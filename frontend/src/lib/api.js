/**
 * HTTP client for the Harness Module API.
 * All methods take (url, apiKey) — callers pull these from config store.
 */

// ── Connection health check ─────────────────────────────────────────────────
// Returns an object: { state, detail, progress, statusData }
export async function checkHealth(url, apiKey) {
  const base = url.replace(/\/$/, '');

  // Step 1: /health (unauthenticated) — determines reachability and install state
  let healthData;
  try {
    const res = await fetchWithTimeout(`${base}/health`, {}, 5000);
    healthData = await res.json();
  } catch (e) {
    return { state: 'unreachable', detail: e.message, progress: 0, statusData: null };
  }

  const moduleStatus = healthData.status ?? 'ready';

  if (moduleStatus === 'starting')   return { state: 'starting',   detail: healthData.message ?? '', progress: 0,                     statusData: null };
  if (moduleStatus === 'installing') return { state: 'installing', detail: healthData.message ?? '', progress: healthData.progress ?? 0, statusData: null };
  if (moduleStatus === 'updating')   return { state: 'updating',   detail: healthData.message ?? '', progress: healthData.progress ?? 0, statusData: null };
  if (moduleStatus === 'error')      return { state: 'error',      detail: healthData.error   ?? '', progress: 0,                     statusData: null };

  // Step 2: /v1/status (authenticated) — determines backend and model state
  if (!apiKey) return { state: 'auth_failed', detail: 'No API key configured', progress: 0, statusData: null };

  let statusRes;
  try {
    statusRes = await fetchWithTimeout(`${base}/v1/status`, { headers: authHeaders(apiKey) }, 5000);
  } catch (e) {
    return { state: 'unreachable', detail: e.message, progress: 0, statusData: null };
  }

  if (statusRes.status === 401) return { state: 'auth_failed', detail: 'Invalid API key', progress: 0, statusData: null };
  if (!statusRes.ok)            return { state: 'error', detail: `HTTP ${statusRes.status}`, progress: 0, statusData: null };

  const sd = await statusRes.json();

  if (!sd.ok)           return { state: 'backend_down', detail: `${sd.backend} not responding`, progress: 0, statusData: sd };
  if (!sd.model_loaded) return { state: 'no_model',     detail: 'No model loaded',              progress: 0, statusData: sd };

  return { state: 'ready', detail: '', progress: 1, statusData: sd };
}

// ── Models ─────────────────────────────────────────────────────────────────
export async function listModels(url, apiKey) {
  const res = await apiFetch(url, apiKey, '/v1/models');
  return res.json();
}

export async function loadModel(url, apiKey, modelId) {
  const res = await apiFetch(url, apiKey, '/v1/models/load', {
    method: 'POST',
    body: JSON.stringify({ model_id: modelId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Failed to load model: HTTP ${res.status}`);
  }
  return res.json();
}

export async function unloadModel(url, apiKey) {
  const res = await apiFetch(url, apiKey, '/v1/models/unload', { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Failed to unload model: HTTP ${res.status}`);
  }
  return res.json();
}

// ── Chat (SSE streaming) ─────────────────────────────────────────────────────
// Yields: { type: 'token'|'done'|'error', content?, usage?, latency_ms?, ... }
export async function* chatStream(url, apiKey, payload, signal) {
  const res = await apiFetch(url, apiKey, '/v1/chat', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    yield { type: 'error', message: err.detail ?? 'Request failed' };
    return;
  }

  yield* parseSSEStream(res.body);
}

// ── Image generation ─────────────────────────────────────────────────────────
export async function generateImage(url, apiKey, payload) {
  const res = await apiFetch(url, apiKey, '/v1/generate/image', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Generation failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function listCheckpoints(url, apiKey) {
  const res = await apiFetch(url, apiKey, '/v1/generate/checkpoints');
  if (!res.ok) return { checkpoints: [] };
  return res.json();
}

// ── Model manifest ───────────────────────────────────────────────────────────
export async function addModelToManifest(url, apiKey, entry) {
  const res = await apiFetch(url, apiKey, '/v1/admin/models', {
    method: 'POST',
    body: JSON.stringify(entry),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? `Failed to add model: HTTP ${res.status}`);
  }
  return res.json();
}

// ── Sessions ─────────────────────────────────────────────────────────────────
export async function resetContext(url, apiKey, characterId) {
  const res = await apiFetch(url, apiKey, `/v1/context/reset?character_id=${encodeURIComponent(characterId)}`, { method: 'POST' });
  return res.json();
}

// ── Internals ─────────────────────────────────────────────────────────────────
function authHeaders(apiKey) {
  return { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' };
}

async function apiFetch(url, apiKey, path, opts = {}) {
  const base = url.replace(/\/$/, '');
  return fetch(`${base}${path}`, {
    ...opts,
    headers: { ...authHeaders(apiKey), ...(opts.headers ?? {}) },
  });
}

async function fetchWithTimeout(url, opts, ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetch(url, { ...opts, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function* parseSSEStream(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        try { yield JSON.parse(line.slice(6)); } catch { /* malformed line */ }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
