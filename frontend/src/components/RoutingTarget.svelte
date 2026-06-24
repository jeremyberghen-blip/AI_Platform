<script>
  import { routingTarget, statusData, config } from '../lib/stores.js';

  // Backend type → display label
  const BACKEND_LABELS = { ollama: 'Ollama', comfyui: 'ComfyUI', unknown: '—' };

  $: label = $routingTarget ? BACKEND_LABELS[$routingTarget.backend] ?? $routingTarget.backend : '—';
  $: host  = $routingTarget?.host ?? '—';

  // Distinguish local vs. remote
  $: isLocal = host.startsWith('localhost') || host.startsWith('127.') || host.startsWith('0.0.0.');
  $: locationTag = !$routingTarget ? '' : isLocal ? 'local' : 'remote';
</script>

<div class="routing-target">
  <div class="section-label">Routing Target</div>
  <div class="target-box">
    <div class="backend-row">
      <span class="backend-name">{label}</span>
      {#if locationTag}
        <span class="location-tag" class:remote={!isLocal}>{locationTag}</span>
      {/if}
    </div>
    <div class="host">{host}</div>
    {#if $statusData?.model_loaded}
      <div class="model-chip">{$statusData.model_loaded}</div>
    {/if}
  </div>
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

  .target-box {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .backend-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .backend-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--text);
  }

  .location-tag {
    font-size: 10px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--status-ready);
    background: #1a3a2a;
    border-radius: 3px;
    padding: 1px 5px;
  }
  .location-tag.remote {
    color: var(--status-info);
    background: var(--accent-dim);
  }

  .host {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
    word-break: break-all;
  }

  .model-chip {
    margin-top: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--accent);
    background: var(--accent-glow);
    border-radius: 3px;
    padding: 2px 6px;
    display: inline-block;
    width: fit-content;
  }
</style>
