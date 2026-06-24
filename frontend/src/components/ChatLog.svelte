<script>
  import ChatMessage from './ChatMessage.svelte';
  import { messages, connectionState } from '../lib/stores.js';
  import { afterUpdate } from 'svelte';

  let logEl;

  afterUpdate(() => {
    if (logEl) logEl.scrollTop = logEl.scrollHeight;
  });

  // Status banners for non-ready states
  const STATE_BANNERS = {
    unreachable:  { icon: '⚠', text: 'Cannot reach the harness module. Check the URL in Settings.' },
    auth_failed:  { icon: '🔑', text: 'Authentication failed. Check your API key in Settings.' },
    backend_down: { icon: '⚠', text: 'Module is running but the backend (Ollama) is not responding.' },
    no_model:     { icon: '○', text: 'No model loaded. Select a model in the sidebar and click Load.' },
    installing:   { icon: '↓', text: 'First-time installation in progress. This may take several minutes.' },
    updating:     { icon: '↻', text: 'Applying update. The module will restart shortly.' },
    starting:     { icon: '◌', text: 'Module is starting up…' },
    error:        { icon: '✕', text: 'Module reported an error. Check connection details.' },
  };

  $: banner = STATE_BANNERS[$connectionState] ?? null;
</script>

<div class="chat-log" bind:this={logEl}>
  {#if banner && !$messages.length}
    <div class="state-banner">
      <span class="banner-icon">{banner.icon}</span>
      <span class="banner-text">{banner.text}</span>
    </div>
  {/if}

  {#if !$messages.length && $connectionState === 'ready'}
    <div class="empty-state">
      <div class="empty-icon">◈</div>
      <div class="empty-text">Start a conversation</div>
    </div>
  {/if}

  {#each $messages as msg (msg.id)}
    <ChatMessage
      role={msg.role}
      content={msg.content}
      tokens={msg.tokens}
      latencyMs={msg.latency_ms}
      streaming={msg.streaming}
    />
  {/each}
</div>

<style>
  .chat-log {
    flex: 1;
    overflow-y: auto;
    padding: 20px 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .state-banner {
    margin: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 18px;
    max-width: 480px;
    color: var(--text-muted);
    font-size: 13px;
    line-height: 1.5;
  }

  .banner-icon {
    font-size: 18px;
    flex-shrink: 0;
    opacity: 0.7;
  }

  .empty-state {
    margin: auto;
    text-align: center;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }

  .empty-icon {
    font-size: 32px;
    opacity: 0.3;
  }

  .empty-text {
    font-size: 14px;
    color: var(--text-dim);
  }
</style>
