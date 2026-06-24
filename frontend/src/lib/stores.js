import { writable, derived } from 'svelte/store';
import { loadConfig, activeProfile } from './config.js';

// ── Config ─────────────────────────────────────────────────
export const config = writable(loadConfig());

// ── Connection ─────────────────────────────────────────────
// States: unreachable | starting | installing | updating | auth_failed
//         backend_down | no_model | ready | error
export const connectionState = writable('unreachable');
export const connectionDetail = writable('');   // human-readable extra info
export const installProgress  = writable(0);    // 0–1 during installing/updating
export const statusData       = writable(null); // last /v1/status response

// ── Models ─────────────────────────────────────────────────
export const availableModels  = writable([]);
export const selectedModel    = writable('');

// ── Chat ───────────────────────────────────────────────────
export const messages    = writable([]);  // { id, role, content, tokens, latency_ms, streaming }
export const isStreaming = writable(false);

// ── UI ─────────────────────────────────────────────────────
export const showSettings = writable(false);

// ── Active profile URL (derived from config) ───────────────
export const moduleUrl = derived(config, c => activeProfile(c)?.moduleUrl ?? '');

// ── Derived ────────────────────────────────────────────────
export const isReady = derived(connectionState, s => s === 'ready');

export const canChat = derived(
  [connectionState, isStreaming],
  ([cs, streaming]) => cs === 'ready' && !streaming,
);

export const routingTarget = derived(statusData, sd => {
  if (!sd) return null;
  const url = sd.backend_url ?? '';
  let host = url;
  try { host = new URL(url).hostname + (new URL(url).port ? ':' + new URL(url).port : ''); } catch {}
  return { backend: sd.backend ?? 'unknown', host };
});

export const statusColor = derived(connectionState, s => ({
  ready:        'var(--status-ready)',
  no_model:     'var(--status-warning)',
  backend_down: 'var(--status-caution)',
  installing:   'var(--status-info)',
  updating:     'var(--status-info)',
  starting:     'var(--status-info)',
  auth_failed:  'var(--status-error)',
  unreachable:  'var(--status-error)',
  error:        'var(--status-error)',
}[s] ?? 'var(--text-dim)'));

export const statusLabel = derived(connectionState, s => ({
  ready:        'Ready',
  no_model:     'No Model',
  backend_down: 'Backend Down',
  installing:   'Installing',
  updating:     'Updating',
  starting:     'Starting',
  auth_failed:  'Auth Failed',
  unreachable:  'Unreachable',
  error:        'Error',
}[s] ?? s));
