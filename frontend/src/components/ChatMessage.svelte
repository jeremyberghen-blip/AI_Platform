<script>
  export let role    = 'user';   // 'user' | 'assistant'
  export let content = '';
  export let tokens  = null;
  export let latencyMs = null;
  export let streaming = false;

  $: isUser = role === 'user';
</script>

<div class="message" class:user={isUser} class:assistant={!isUser}>
  <div class="role-tag">{isUser ? 'You' : 'AI'}</div>
  <div class="bubble">
    <div class="content">{content}{#if streaming}<span class="cursor">▋</span>{/if}</div>
    {#if !streaming && (tokens || latencyMs)}
      <div class="meta">
        {#if tokens}<span>{tokens} tokens</span>{/if}
        {#if tokens && latencyMs}<span class="sep">·</span>{/if}
        {#if latencyMs}<span>{latencyMs}ms</span>{/if}
      </div>
    {/if}
  </div>
</div>

<style>
  .message {
    display: flex;
    gap: 10px;
    padding: 4px 0;
    animation: fadeIn 0.12s ease;
  }

  .message.user { flex-direction: row-reverse; }

  .role-tag {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-dim);
    padding-top: 6px;
    flex-shrink: 0;
    width: 28px;
    text-align: center;
  }

  .bubble {
    max-width: 72%;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .user .bubble { align-items: flex-end; }
  .assistant .bubble { align-items: flex-start; }

  .content {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
    line-height: 1.6;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
  }

  .user .content {
    background: var(--accent-dim);
    border-color: var(--accent);
    color: var(--text);
    border-bottom-right-radius: 3px;
  }

  .assistant .content {
    border-bottom-left-radius: 3px;
  }

  .cursor {
    display: inline-block;
    animation: pulse 0.8s ease-in-out infinite;
    color: var(--accent);
    margin-left: 1px;
  }

  .meta {
    font-size: 10px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    display: flex;
    gap: 4px;
    padding: 0 2px;
  }

  .sep { opacity: 0.5; }
</style>
