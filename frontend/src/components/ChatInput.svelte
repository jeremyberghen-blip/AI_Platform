<script>
  import { canChat, isStreaming, messages, pushMessage, updateMessage, config, moduleUrl } from '../lib/stores.js';
  import { chatStream } from '../lib/api.js';
  import { API_KEY } from '../lib/config.js';
  import { get } from 'svelte/store';

  let text = '';
  let textareaEl;
  let controller = null;

  function autoResize() {
    if (!textareaEl) return;
    textareaEl.style.height = 'auto';
    textareaEl.style.height = Math.min(textareaEl.scrollHeight, 200) + 'px';
  }

  function handleKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  async function send() {
    const input = text.trim();
    if (!input || !$canChat) return;
    text = '';
    setTimeout(autoResize, 0);

    const cfg = get(config);
    const characterId = cfg.activeCharacter;

    // Add user message
    const userMsg = { id: Date.now(), role: 'user', content: input };
    pushMessage(characterId, userMsg);

    // Add streaming placeholder
    const assistantId = Date.now() + 1;
    const assistantMsg = { id: assistantId, role: 'assistant', content: '', streaming: true };
    pushMessage(characterId, assistantMsg);

    isStreaming.set(true);
    controller = new AbortController();

    // Build messages array for the API
    const currentMessages = get(messages)
      .filter(m => !m.streaming)
      .map(m => ({ role: m.role, content: m.content }));

    const payload = {
      character_id: cfg.activeCharacter,
      messages: currentMessages,
      system_prompt: '',
      params: { temperature: 0.8, max_tokens: 2048 },
    };

    try {
      for await (const chunk of chatStream(get(moduleUrl), API_KEY, payload, controller.signal)) {
        if (chunk.type === 'token') {
          updateMessage(characterId, assistantId, m => ({ ...m, content: m.content + chunk.content }));
        } else if (chunk.type === 'done') {
          updateMessage(characterId, assistantId, m => ({
            ...m, streaming: false, tokens: chunk.usage?.completion_tokens, latency_ms: chunk.latency_ms,
          }));
        } else if (chunk.type === 'error') {
          updateMessage(characterId, assistantId, m => ({
            ...m, streaming: false, content: `[Error: ${chunk.message}]`,
          }));
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        updateMessage(characterId, assistantId, m => ({ ...m, streaming: false, content: `[Error: ${e.message}]` }));
      } else {
        updateMessage(characterId, assistantId, m => ({ ...m, streaming: false }));
      }
    } finally {
      isStreaming.set(false);
      controller = null;
    }
  }

  function cancelStream() {
    controller?.abort();
  }
</script>

<div class="input-area">
  <div class="input-row">
    <textarea
      bind:this={textareaEl}
      bind:value={text}
      on:keydown={handleKeydown}
      on:input={autoResize}
      placeholder={$canChat ? 'Message… (Enter to send, Shift+Enter for newline)' : 'Not ready'}
      disabled={!$canChat && !$isStreaming}
      rows="1"
    ></textarea>

    {#if $isStreaming}
      <button class="action-btn stop" on:click={cancelStream} title="Stop">■</button>
    {:else}
      <button
        class="action-btn send"
        on:click={send}
        disabled={!$canChat || !text.trim()}
        title="Send (Enter)"
      >➤</button>
    {/if}
  </div>
</div>

<style>
  .input-area {
    padding: 12px 20px 16px;
    border-top: 1px solid var(--border);
    background: var(--surface);
    flex-shrink: 0;
  }

  .input-row {
    display: flex;
    gap: 8px;
    align-items: flex-end;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 8px 8px 8px 14px;
    transition: border-color 0.15s;
  }
  .input-row:focus-within { border-color: var(--accent); }

  textarea {
    flex: 1;
    background: transparent;
    border: none;
    padding: 0;
    resize: none;
    min-height: 24px;
    max-height: 200px;
    overflow-y: auto;
    line-height: 1.5;
    color: var(--text);
    font-size: 14px;
    border-radius: 0;
  }
  textarea::placeholder { color: var(--text-dim); }
  textarea:focus { outline: none; }
  textarea:disabled { opacity: 0.4; cursor: not-allowed; }

  .action-btn {
    flex-shrink: 0;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    font-size: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.15s, color 0.15s;
  }

  .send {
    background: var(--accent);
    color: var(--bg);
  }
  .send:hover:not(:disabled) { opacity: 0.85; }
  .send:disabled { background: var(--surface-3); color: var(--text-dim); cursor: not-allowed; }

  .stop {
    background: var(--surface-3);
    color: var(--status-error);
    border: 1px solid var(--status-error);
    font-size: 11px;
  }
  .stop:hover { background: var(--status-error); color: white; }
</style>
