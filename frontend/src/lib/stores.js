import { writable, derived } from 'svelte/store';
import { loadConfig, activeProfile } from './config.js';

// ── Config ─────────────────────────────────────────────
export const config = writable(loadConfig());

// ── Connection ─────────────────────────────────────────
// States: unreachable | starting | installing | updating | auth_failed
//         backend_down | no_model | ready | error
export const connectionState  = writable('unreachable');
export const connectionDetail = writable('');
export const installProgress  = writable(0);
export const statusData       = writable(null);

// ── Models ─────────────────────────────────────────────
export const availableModels = writable([]);
export const selectedModel   = writable('');

// ── Chat ───────────────────────────────────────────────
const HISTORIES_KEY = 'ai_harness_chat_histories';
function loadHistories() {
  try { return JSON.parse(localStorage.getItem(HISTORIES_KEY) ?? '{}'); } catch { return {}; }
}
export const chatHistories = writable(loadHistories());
chatHistories.subscribe(h => {
  try { localStorage.setItem(HISTORIES_KEY, JSON.stringify(h)); } catch {}
});

export const messages = derived(
  [chatHistories, config],
  ([h, cfg]) => h[cfg.activeCharacter] ?? []
);

export function pushMessage(characterId, msg) {
  chatHistories.update(h => ({ ...h, [characterId]: [...(h[characterId] ?? []), msg] }));
}

export function updateMessage(characterId, id, updater) {
  chatHistories.update(h => ({
    ...h,
    [characterId]: (h[characterId] ?? []).map(m => m.id === id ? updater(m) : m),
  }));
}

export function clearHistory(characterId) {
  chatHistories.update(h => ({ ...h, [characterId]: [] }));
}

export const isStreaming = writable(false);

// ── Sable mode ─────────────────────────────────────────
const SABLE_MODE_KEY = 'sable_mode';
function loadSableMode() {
  try {
    const v = localStorage.getItem(SABLE_MODE_KEY);
    return (v === 'sfw' || v === 'nsfw') ? v : 'sfw';
  } catch { return 'sfw'; }
}
export const sableMode           = writable(loadSableMode());
export const sableLoading        = writable(false);
export const sableProductionMode = writable(false); // resets each session intentionally
export const sableFallback       = writable(false); // true when prescribed model not found
sableMode.subscribe(m => {
  try { localStorage.setItem(SABLE_MODE_KEY, m); } catch {}
});

// ── UI ─────────────────────────────────────────────────
export const showSettings = writable(false);

// ── Active profile URL ─────────────────────────────────
export const moduleUrl = derived(config, c => activeProfile(c)?.moduleUrl ?? '');

// ── Derived ────────────────────────────────────────────
export const isReady = derived(connectionState, s => s === 'ready');

export const canChat = derived(
  [connectionState, isStreaming, sableLoading, sableProductionMode, config],
  ([cs, streaming, sl, prod, cfg]) => {
    if (cs !== 'ready' || streaming || sl) return false;
    if (cfg.activeCharacter === 'sable' && prod) return false;
    return true;
  }
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
