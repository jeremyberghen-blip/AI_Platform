<script>
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import { sableMode, sableLoading, statusData, moduleUrl } from '../lib/stores.js';
  import { loadModel, unloadModel } from '../lib/api.js';
  import { API_KEY } from '../lib/config.js';

  export let onModelLoaded = () => {};

  const CHAT_MODELS = {
    sfw:  'llama3.3:70b',
    nsfw: 'dolphin-llama3:70b',
  };

  const TOOL_PORTS = { comfy: 8188, kohya: 8552 };

  let error      = '';
  let activeTool = null; // 'comfy' | 'kohya' | null
  let toolTab    = null;
  let tabPoll    = null;

  $: isNsfw    = $sableMode === 'nsfw';
  $: inStudio  = activeTool !== null;

  function toolUrl(harnessUrl, port) {
    try {
      const u = new URL(harnessUrl);
      if (u.hostname.includes('.proxy.runpod.net')) {
        return harnessUrl.replace(/-(\d+)\.proxy\.runpod\.net/, `-${port}.proxy.runpod.net`);
      }
      u.port = String(port);
      return u.href;
    } catch { return `http://localhost:${port}`; }
  }

  // Reactive: clear loading once correct model confirmed loaded
  $: if ($sableLoading && !inStudio && $statusData?.model_loaded === CHAT_MODELS[$sableMode]) {
    sableLoading.set(false);
  }

  async function openTool(tool) {
    if ($sableLoading || activeTool === tool) return;
    sableLoading.set(true);
    error = '';
    try {
      await unloadModel(get(moduleUrl), API_KEY);
    } catch (e) {
      error = e.message;
      sableLoading.set(false);
      return;
    }
    activeTool = tool;
    sableLoading.set(false);

    clearInterval(tabPoll);
    toolTab = window.open(toolUrl(get(moduleUrl), TOOL_PORTS[tool]), '_blank');
    tabPoll = setInterval(() => {
      if (!toolTab || toolTab.closed) returnToChat();
    }, 2000);
  }

  async function returnToChat() {
    clearInterval(tabPoll);
    tabPoll    = null;
    toolTab    = null;
    activeTool = null;
    error      = '';
    sableLoading.set(true);
    try {
      await loadModel(get(moduleUrl), API_KEY, CHAT_MODELS[get(sableMode)]);
      onModelLoaded();
    } catch (e) {
      error = e.message;
      sableLoading.set(false);
    }
  }

  async function handleContentMode(next) {
    if ($sableLoading || inStudio || $sableMode === next) return;
    sableMode.set(next);
    sableLoading.set(true);
    error = '';
    try {
      await loadModel(get(moduleUrl), API_KEY, CHAT_MODELS[next]);
      onModelLoaded();
    } catch (e) {
      error = e.message;
      sableLoading.set(false);
    }
  }

  // Auto-load on mount if the wrong model is loaded
  onMount(() => {
    const loaded   = get(statusData)?.model_loaded ?? null;
    const required = CHAT_MODELS[get(sableMode)];
    if (loaded !== required) {
      sableLoading.set(true);
      loadModel(get(moduleUrl), API_KEY, required)
        .then(onModelLoaded)
        .catch(e => { error = e.message; sableLoading.set(false); });
    }
  });

  onDestroy(() => clearInterval(tabPoll));
</script>

<div class="mode-bar" class:nsfw={isNsfw} class:studio={inStudio}>
  <span class="agent-label">Sable · Media</span>

  <div class="mode-controls">
    {#if $sableLoading}
      <span class="loading-text">{inStudio ? 'Returning…' : 'Loading…'}</span>
    {:else if error}
      <span class="error-text" title={error}>Error</span>
    {/if}

    <!-- SFW / NSFW — disabled while loading or in studio -->
    <div class="pill-group" class:disabled={$sableLoading || inStudio}>
      <button
        class="mode-pill"
        class:active={!isNsfw}
        disabled={$sableLoading || inStudio}
        on:click={() => handleContentMode('sfw')}
      >SFW</button>
      <button
        class="mode-pill"
        class:active={isNsfw}
        disabled={$sableLoading || inStudio}
        on:click={() => handleContentMode('nsfw')}
      >NSFW</button>
    </div>

    <!-- Tool buttons -->
    {#if activeTool === 'comfy'}
      <button class="tool-btn active" on:click={returnToChat} disabled={$sableLoading}>● ComfyUI</button>
    {:else}
      <button class="tool-btn" on:click={() => openTool('comfy')} disabled={$sableLoading || inStudio}>ComfyUI →</button>
    {/if}

    {#if activeTool === 'kohya'}
      <button class="tool-btn active" on:click={returnToChat} disabled={$sableLoading}>● Kohya</button>
    {:else}
      <button class="tool-btn" on:click={() => openTool('kohya')} disabled={$sableLoading || inStudio}>Kohya →</button>
    {/if}
  </div>
</div>

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
    transition: border-color 0.2s;
  }
  .mode-bar.nsfw:not(.studio) { border-bottom-color: var(--status-caution); }
  .mode-bar.studio             { border-bottom-color: var(--accent); }

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
  .mode-bar.nsfw:not(.studio) .mode-pill.active {
    background: var(--status-caution);
    color: var(--bg);
  }
  .mode-pill:disabled { cursor: default; }

  .tool-btn {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid var(--accent);
    color: var(--accent);
    background: transparent;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .tool-btn:hover:not(:disabled) { background: var(--accent); color: var(--bg); }
  .tool-btn.active {
    background: var(--accent-dim);
    color: var(--accent);
    animation: pulse 2s ease-in-out infinite;
  }
  .tool-btn:disabled { opacity: 0.4; cursor: default; }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.6; }
  }
</style>
