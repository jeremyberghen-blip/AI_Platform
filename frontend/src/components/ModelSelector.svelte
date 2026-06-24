<script>
  import { availableModels, selectedModel, statusData, connectionState, moduleUrl } from '../lib/stores.js';
  import { loadModel } from '../lib/api.js';
  import { API_KEY } from '../lib/config.js';
  import { get } from 'svelte/store';

  export let onModelLoaded = () => {};

  let loading = false;
  let error = '';

  $: loadedModel = $statusData?.model_loaded ?? null;
  $: canLoad = $connectionState !== 'unreachable' && $connectionState !== 'auth_failed' && $selectedModel;

  async function handleLoad() {
    if (!$selectedModel || loading) return;
    loading = true;
    error = '';
    try {
        await loadModel(get(moduleUrl), API_KEY, $selectedModel);
      onModelLoaded();
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="model-selector">
  <div class="section-label">Model</div>

  <div class="select-row">
    <select bind:value={$selectedModel} disabled={!$availableModels.length}>
      {#if !$availableModels.length}
        <option value="">No models available</option>
      {:else}
        <option value="" disabled>Select model…</option>
        {#each $availableModels as m}
          <option value={m.model_id}>
            {m.model_id}
            {#if m.size_mb}{' '}({Math.round(m.size_mb / 1024 * 10) / 10}GB){/if}
          </option>
        {/each}
      {/if}
    </select>

    <button
      class="load-btn"
      on:click={handleLoad}
      disabled={!canLoad || loading || $selectedModel === loadedModel}
      title={$selectedModel === loadedModel ? 'Already loaded' : 'Load model'}
    >
      {loading ? '…' : $selectedModel === loadedModel ? '✓' : 'Load'}
    </button>
  </div>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if loadedModel && $selectedModel !== loadedModel}
    <div class="loaded-note">Loaded: {loadedModel}</div>
  {/if}
</div>

<style>
  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 6px;
  }

  .select-row {
    display: flex;
    gap: 6px;
  }

  select {
    flex: 1;
    min-width: 0;
    font-size: 12px;
    padding: 6px 8px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    cursor: pointer;
  }
  select:disabled { opacity: 0.4; cursor: default; }

  .load-btn {
    flex-shrink: 0;
    background: var(--accent-dim);
    border: 1px solid var(--accent);
    color: var(--accent);
    border-radius: var(--radius);
    padding: 0 12px;
    font-size: 12px;
    font-weight: 600;
    transition: background 0.15s;
  }
  .load-btn:hover:not(:disabled) { background: var(--accent); color: var(--bg); }
  .load-btn:disabled { opacity: 0.35; cursor: default; }

  .error {
    font-size: 11px;
    color: var(--status-error);
    margin-top: 4px;
  }

  .loaded-note {
    font-size: 11px;
    color: var(--text-dim);
    margin-top: 4px;
    font-family: var(--font-mono);
  }
</style>
