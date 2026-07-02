<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { sableMode, sableLoading, sableProductionMode, sableFallback, statusData, moduleUrl } from '../lib/stores.js';
  import { loadModel, unloadModel } from '../lib/api.js';
  import { API_KEY } from '../lib/config.js';
  import AddModelDialog from './AddModelDialog.svelte';

  let showAddModel = false;

  export let onModelLoaded = () => {};

  const CHAT_MODELS = {
    sfw:  'llama3.3:70b',
    nsfw: 'dolphin-llama3:70b',
  };

  const TOOL_PORTS = { comfy: 8188, kohya: 8552 };

  let error = '';

  $: isNsfw = $sableMode === 'nsfw';
  $: isProd  = $sableProductionMode;

  function toolUrl(port) {
    try {
      const u = new URL(get(moduleUrl));
      if (u.hostname.includes('.proxy.runpod.net')) {
        return get(moduleUrl).replace(/-(\d+)\.proxy\.runpod\.net/, `-${port}.proxy.runpod.net`);
      }
      u.port = String(port);
      return u.href;
    } catch { return `http://localhost:${port}`; }
  }

  // Clear loading once the correct model is confirmed loaded
  $: if ($sableLoading && !isProd && $statusData?.model_loaded === CHAT_MODELS[$sableMode]) {
    sableLoading.set(false);
  }

  async function toggleProductionMode() {
    // Allow entering production mode even while loading — unload acts as cancel
    if (!get(sableProductionMode) && get(sableLoading)) {
      // Force-clear stuck load state then unload
      sableLoading.set(false);
    }
    if (get(sableProductionMode) && get(sableLoading)) return; // don't exit while reloading
    error = '';
    const entering = !get(sableProductionMode);
    sableLoading.set(true);
    try {
      if (entering) {
        await unloadModel(get(moduleUrl), API_KEY);
        sableProductionMode.set(true);
        sableLoading.set(false);
      } else {
        sableProductionMode.set(false);
        await tryLoadPrescribed(CHAT_MODELS[get(sableMode)]);
      }
    } catch (e) {
      error = e.message;
      sableLoading.set(false);
    }
  }

  async function handleContentMode(next) {
    if ($sableLoading || isProd || $sableMode === next) return;
    sableMode.set(next);
    await tryLoadPrescribed(CHAT_MODELS[next]);
  }

  async function tryLoadPrescribed(modelId) {
    sableLoading.set(true);
    sableFallback.set(false);
    error = '';
    try {
      await loadModel(get(moduleUrl), API_KEY, modelId);
      sableLoading.set(false);
      onModelLoaded();
    } catch (e) {
      sableLoading.set(false);
      // Model not found locally — hand control back to the user
      sableFallback.set(true);
      error = `${modelId} not found — select a model manually`;
    }
  }

  // Auto-load on mount only if no model is currently loaded
  onMount(() => {
    const loaded = get(statusData)?.model_loaded ?? null;
    if (loaded || get(sableProductionMode)) return;
    tryLoadPrescribed(CHAT_MODELS[get(sableMode)]);
  });
</script>

<div class="mode-bar" class:nsfw={isNsfw} class:production={isProd}>
  <span class="agent-label">Sable · Media</span>

  <div class="mode-controls">
    {#if $sableLoading}
      <span class="loading-text">Loading…</span>
    {:else if error}
      <span class="error-text" title={error}>Error</span>
    {/if}

    <!-- SFW / NSFW — disabled in production mode or while loading -->
    <div class="pill-group" class:disabled={$sableLoading || isProd}>
      <button
        class="mode-pill"
        class:active={!isNsfw}
        disabled={$sableLoading || isProd}
        on:click={() => handleContentMode('sfw')}
      >SFW</button>
      <button
        class="mode-pill"
        class:active={isNsfw}
        disabled={$sableLoading || isProd}
        on:click={() => handleContentMode('nsfw')}
      >NSFW</button>
    </div>

    <!-- Production Mode toggle -->
    <button
      class="prod-toggle"
      class:active={isProd}
      on:click={toggleProductionMode}
    >
      {isProd ? '● Production' : 'Production Mode'}
    </button>

    <!-- Tool links — always open in new tab, no state change -->
    <a class="tool-link" href={toolUrl(TOOL_PORTS.comfy)} target="_blank" rel="noreferrer">ComfyUI →</a>
    <a class="tool-link" href={toolUrl(TOOL_PORTS.kohya)} target="_blank" rel="noreferrer">Kohya →</a>

    <button class="tool-link" on:click={() => (showAddModel = true)}>+ Model</button>
  </div>
</div>

{#if showAddModel}
  <AddModelDialog onClose={() => (showAddModel = false)} />
{/if}

<style>
  .mode-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 16px;
    height: 36px;
    flex-shrink: 0;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    transition: border-color 0.2s, background 0.2s;
  }
  .mode-bar.nsfw:not(.production) { border-bottom-color: var(--status-caution); }
  .mode-bar.production            { border-bottom-color: var(--accent); background: color-mix(in srgb, var(--accent) 6%, var(--surface)); }

  .agent-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .mode-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .loading-text {
    font-size: 11px;
    color: var(--status-info);
    font-family: var(--font-mono);
  }

  .error-text {
    font-size: 11px;
    color: var(--status-error);
    font-family: var(--font-mono);
    cursor: help;
  }

  .pill-group {
    display: flex;
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
    transition: opacity 0.15s;
  }
  .pill-group.disabled { opacity: 0.35; pointer-events: none; }

  .mode-pill {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 3px 12px;
    border: none;
    background: transparent;
    color: var(--text-dim);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .mode-pill + .mode-pill { border-left: 1px solid var(--border); }
  .mode-pill:hover:not(:disabled):not(.active) {
    color: var(--text);
    background: var(--surface-2);
  }
  .mode-pill.active { background: var(--accent); color: var(--bg); }
  .mode-bar.nsfw:not(.production) .mode-pill.active {
    background: var(--status-caution);
    color: var(--bg);
  }
  .mode-pill:disabled { cursor: default; }

  .prod-toggle {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    color: var(--text-dim);
    background: transparent;
    cursor: pointer;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  .prod-toggle:hover:not(:disabled) {
    border-color: var(--accent);
    color: var(--accent);
  }
  .prod-toggle.active {
    border-color: var(--accent);
    background: var(--accent);
    color: var(--bg);
    animation: pulse 2s ease-in-out infinite;
  }
  .prod-toggle:disabled { opacity: 0.4; cursor: default; }

  .tool-link {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    color: var(--text-dim);
    background: transparent;
    text-decoration: none;
    transition: border-color 0.12s, color 0.12s;
  }
  .tool-link:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.6; }
  }
</style>
