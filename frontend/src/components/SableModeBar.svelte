<script>
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { sableMode, sableWorkMode, sableLoading, statusData, moduleUrl } from '../lib/stores.js';
  import { loadModel, unloadModel } from '../lib/api.js';
  import { API_KEY } from '../lib/config.js';

  export let onModelLoaded = () => {};

  // Chat mode model targets. Studio mode unloads the 70B entirely.
  // When llama3.2-vision:11b is pulled, set STUDIO_MODEL to it.
  const CHAT_MODELS = {
    sfw:  'llama3.3:70b',
    nsfw: 'dolphin-llama3:70b',
  };
  const STUDIO_MODEL = null; // set to 'llama3.2-vision:11b' once pulled

  let error = '';

  $: isStudio  = $sableWorkMode === 'studio';
  $: isNsfw    = $sableMode === 'nsfw';

  // Required model for current state: studio uses vision model (or nothing), chat uses 70B
  $: requiredModel = isStudio
    ? (STUDIO_MODEL ?? null)
    : CHAT_MODELS[$sableMode];

  // Clear loading once statusData reflects the correct state
  $: {
    if ($sableLoading) {
      const loaded = $statusData?.model_loaded ?? null;
      if (requiredModel === null && !loaded) {
        sableLoading.set(false);
      } else if (requiredModel && loaded === requiredModel) {
        sableLoading.set(false);
      }
    }
  }

  async function applyCurrentState() {
    sableLoading.set(true);
    error = '';
    try {
      if (requiredModel === null) {
        await unloadModel(get(moduleUrl), API_KEY);
      } else {
        await loadModel(get(moduleUrl), API_KEY, requiredModel);
      }
      onModelLoaded();
    } catch (e) {
      error = e.message;
      sableLoading.set(false);
    }
  }

  async function handleWorkMode(next) {
    if ($sableLoading || $sableWorkMode === next) return;
    sableWorkMode.set(next);
    await applyCurrentState();
  }

  async function handleContentMode(next) {
    if ($sableLoading || $sableMode === next || isStudio) return;
    sableMode.set(next);
    await applyCurrentState();
  }

  // Auto-load on mount: sync model to current mode
  onMount(() => {
    const loaded = get(statusData)?.model_loaded ?? null;
    const required = requiredModel;
    const needsChange = required === null ? !!loaded : loaded !== required;
    if (needsChange) applyCurrentState();
  });
</script>

<div class="mode-bar" class:nsfw={isNsfw} class:studio={isStudio}>
  <span class="agent-label">Sable · Media</span>

  <div class="mode-controls">
    {#if $sableLoading}
      <span class="loading-text">Loading…</span>
    {:else if error}
      <span class="error-text" title={error}>Error</span>
    {/if}

    <!-- Chat / Studio -->
    <div class="pill-group" class:disabled={$sableLoading}>
      <button
        class="mode-pill"
        class:active={!isStudio}
        disabled={$sableLoading}
        on:click={() => handleWorkMode('chat')}
      >Chat</button>
      <button
        class="mode-pill studio-pill"
        class:active={isStudio}
        disabled={$sableLoading}
        on:click={() => handleWorkMode('studio')}
      >Studio</button>
    </div>

    <!-- SFW / NSFW — only relevant in Chat mode -->
    <div class="pill-group" class:disabled={$sableLoading || isStudio}>
      <button
        class="mode-pill"
        class:active={!isNsfw}
        disabled={$sableLoading || isStudio}
        on:click={() => handleContentMode('sfw')}
      >SFW</button>
      <button
        class="mode-pill"
        class:active={isNsfw}
        disabled={$sableLoading || isStudio}
        on:click={() => handleContentMode('nsfw')}
      >NSFW</button>
    </div>
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
  .mode-bar.nsfw:not(.studio) {
    border-bottom-color: var(--status-caution);
  }
  .mode-bar.studio {
    border-bottom-color: var(--accent);
  }

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
  .mode-pill + .mode-pill {
    border-left: 1px solid var(--border);
  }
  .mode-pill:hover:not(:disabled):not(.active) {
    color: var(--text);
    background: var(--surface-2);
  }
  .mode-pill.active {
    background: var(--accent);
    color: var(--bg);
  }

  /* NSFW active pill */
  .mode-bar.nsfw:not(.studio) .mode-pill.active:not(.studio-pill) {
    background: var(--status-caution);
    color: var(--bg);
  }

  /* Studio active pill always uses accent */
  .mode-pill.studio-pill.active {
    background: var(--accent);
    color: var(--bg);
  }

  .mode-pill:disabled { cursor: default; }
</style>
