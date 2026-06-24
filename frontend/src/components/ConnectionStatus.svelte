<script>
  import { connectionState, connectionDetail, statusLabel, statusColor, installProgress } from '../lib/stores.js';

  $: animated = ['installing','updating','starting'].includes($connectionState);
  $: showProgress = ['installing','updating'].includes($connectionState);
</script>

<div class="connection-status">
  <div class="status-row">
    <span class="dot" class:animated style="background:{$statusColor}"></span>
    <span class="label">{$statusLabel}</span>
  </div>

  {#if showProgress}
    <div class="progress-bar">
      <div class="progress-fill" style="width:{Math.round($installProgress * 100)}%"></div>
    </div>
  {/if}

  {#if $connectionDetail}
    <div class="detail">{$connectionDetail}</div>
  {/if}
</div>

<style>
  .connection-status {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .status-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    transition: background 0.3s;
  }

  .dot.animated {
    animation: pulse 1.4s ease-in-out infinite;
  }

  .label {
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .progress-bar {
    height: 2px;
    background: var(--border);
    border-radius: 1px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--status-info);
    border-radius: 1px;
    transition: width 0.4s ease;
  }

  .detail {
    font-size: 11px;
    color: var(--text-dim);
    line-height: 1.4;
    word-break: break-all;
  }
</style>
