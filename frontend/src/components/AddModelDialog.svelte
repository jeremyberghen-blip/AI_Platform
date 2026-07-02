<script>
  import { get } from 'svelte/store';
  import { moduleUrl } from '../lib/stores.js';
  import { API_KEY } from '../lib/config.js';
  import { addModelToManifest } from '../lib/api.js';

  export let onClose = () => {};

  const TYPES = ['checkpoint', 'lora', 'controlnet', 'vae', 'upscale'];

  let url      = '';
  let filename = '';
  let type     = 'checkpoint';
  let error    = '';
  let success  = false;
  let loading  = false;

  $: canSubmit = url.trim() && filename.trim() && !loading;

  async function submit() {
    error = '';
    loading = true;
    try {
      await addModelToManifest(get(moduleUrl), API_KEY, {
        type,
        filename: filename.trim().endsWith('.safetensors')
          ? filename.trim()
          : filename.trim() + '.safetensors',
        url: url.trim(),
      });
      success = true;
      setTimeout(onClose, 900);
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  function handleKey(e) {
    if (e.key === 'Escape') onClose();
    if (e.key === 'Enter' && canSubmit) submit();
  }
</script>

<svelte:window on:keydown={handleKey} />

<!-- Backdrop -->
<div class="backdrop" on:click={onClose} role="presentation">
  <div class="dialog" on:click|stopPropagation role="dialog" aria-modal="true" aria-label="Add Model">

    <div class="dialog-header">
      <span class="dialog-title">Add Model to Manifest</span>
      <span class="dialog-sub">Downloaded on next pod start if not already on the volume</span>
    </div>

    <div class="dialog-body">

      <!-- URL -->
      <label class="field">
        <span class="field-label">CivitAI Download URL</span>
        <input
          type="url"
          placeholder="https://civitai.com/api/download/models/…"
          bind:value={url}
          disabled={loading || success}
          autofocus
        />
      </label>

      <!-- Type -->
      <div class="field">
        <span class="field-label">Type</span>
        <div class="type-pills">
          {#each TYPES as t}
            <button
              class="type-pill"
              class:active={type === t}
              disabled={loading || success}
              on:click={() => (type = t)}
            >{t}</button>
          {/each}
        </div>
      </div>

      <!-- Filename -->
      <label class="field">
        <span class="field-label">Filename <span class="field-hint">(.safetensors appended if omitted)</span></span>
        <input
          type="text"
          placeholder="myModel_v1.safetensors"
          bind:value={filename}
          disabled={loading || success}
        />
      </label>

      {#if error}
        <p class="msg error">{error}</p>
      {/if}
      {#if success}
        <p class="msg success">Added — will download on next pod start.</p>
      {/if}
    </div>

    <div class="dialog-footer">
      <button class="btn-cancel" on:click={onClose} disabled={loading}>Cancel</button>
      <button class="btn-add" on:click={submit} disabled={!canSubmit}>
        {loading ? 'Adding…' : 'Add'}
      </button>
    </div>

  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.12s ease;
  }

  .dialog {
    background: var(--surface);
    border: 1px solid var(--border-bright);
    border-radius: calc(var(--radius) * 2);
    width: 480px;
    max-width: calc(100vw - 32px);
    display: flex;
    flex-direction: column;
    gap: 0;
    box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6);
    animation: slideUp 0.15s ease;
  }

  .dialog-header {
    padding: 20px 24px 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .dialog-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
  }

  .dialog-sub {
    font-size: 11px;
    color: var(--text-muted);
  }

  .dialog-body {
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .field-hint {
    font-weight: 400;
    letter-spacing: 0;
    text-transform: none;
    color: var(--text-dim);
  }

  .type-pills {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .type-pill {
    font-size: 11px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    color: var(--text-muted);
    background: transparent;
    cursor: pointer;
    transition: background 0.12s, color 0.12s, border-color 0.12s;
  }
  .type-pill:hover:not(:disabled):not(.active) {
    border-color: var(--border-bright);
    color: var(--text);
  }
  .type-pill.active {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--bg);
  }
  .type-pill:disabled { opacity: 0.4; cursor: default; }

  .msg {
    font-size: 12px;
    padding: 8px 12px;
    border-radius: var(--radius);
  }
  .msg.error   { background: color-mix(in srgb, var(--status-error)   12%, transparent); color: var(--status-error); }
  .msg.success { background: color-mix(in srgb, var(--status-ready)   12%, transparent); color: var(--status-ready); }

  .dialog-footer {
    padding: 16px 24px 20px;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    border-top: 1px solid var(--border);
  }

  .btn-cancel {
    font-size: 12px;
    font-weight: 600;
    padding: 6px 16px;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    color: var(--text-muted);
    background: transparent;
    cursor: pointer;
    transition: border-color 0.12s, color 0.12s;
  }
  .btn-cancel:hover:not(:disabled) {
    border-color: var(--border-bright);
    color: var(--text);
  }
  .btn-cancel:disabled { opacity: 0.4; cursor: default; }

  .btn-add {
    font-size: 12px;
    font-weight: 600;
    padding: 6px 20px;
    border-radius: var(--radius);
    border: 1px solid var(--accent);
    color: var(--bg);
    background: var(--accent);
    cursor: pointer;
    transition: opacity 0.12s;
  }
  .btn-add:hover:not(:disabled) { opacity: 0.85; }
  .btn-add:disabled { opacity: 0.35; cursor: default; }

  @keyframes slideUp {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
</style>
