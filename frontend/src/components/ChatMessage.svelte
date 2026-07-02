<script>
  import { get } from 'svelte/store';
  import { moduleUrl } from '../lib/stores.js';
  import { API_KEY } from '../lib/config.js';
  import { generateImage } from '../lib/api.js';

  export let role      = 'user';
  export let content   = '';
  export let tokens    = null;
  export let latencyMs = null;
  export let streaming = false;

  $: isUser = role === 'user';

  // Split content into plain text and ```comfyui ... ``` blocks.
  // Tracks promptIndex so we know which block is positive vs negative.
  function parseContent(text) {
    const parts = [];
    const regex = /```comfyui\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;
    let promptCount = 0;

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push({ type: 'text', content: text.slice(lastIndex, match.index) });
      }
      parts.push({ type: 'prompt', content: match[1].trim(), promptIndex: promptCount++ });
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      parts.push({ type: 'text', content: text.slice(lastIndex) });
    }
    return parts;
  }

  $: parts = parseContent(content);
  $: hasPromptBlock = parts.some(p => p.type === 'prompt');
  $: promptParts = parts.filter(p => p.type === 'prompt');

  // Per-block copy state
  let copiedIndex = null;

  async function copy(text, i) {
    try {
      await navigator.clipboard.writeText(text);
      copiedIndex = i;
      setTimeout(() => { copiedIndex = null; }, 1800);
    } catch {}
  }

  // Per-message generation state (shared across all blocks in this message)
  let generating = false;
  let genError = '';
  let generatedImage = null; // { src, seed, checkpoint }

  async function generate() {
    if (generating) return;
    generating = true;
    genError = '';
    generatedImage = null;

    // First prompt block = positive, second = negative (Sable's standard output order)
    const positive = promptParts[0]?.content ?? '';
    const negative = promptParts.length > 1 ? promptParts[1].content : '';

    try {
      const result = await generateImage(get(moduleUrl), API_KEY, {
        character_id: 'sable',
        prompt: positive,
        negative_prompt: negative,
        params: {},
      });
      if (result.image_b64) {
        generatedImage = {
          src: `data:image/png;base64,${result.image_b64}`,
          seed: result.seed,
          checkpoint: result.checkpoint,
        };
      } else {
        genError = 'No image returned.';
      }
    } catch (e) {
      genError = e.message ?? 'Generation failed.';
    } finally {
      generating = false;
    }
  }
</script>

<div class="message" class:user={isUser} class:assistant={!isUser}>
  <div class="role-tag">{isUser ? 'You' : 'AI'}</div>
  <div class="bubble">
    <div class="content" class:has-prompt={hasPromptBlock}>
      {#each parts as part, i}
        {#if part.type === 'text'}
          <span class="text-segment">{part.content}</span>
        {:else}
          <div class="prompt-block">
            <div class="prompt-header">
              <span class="prompt-label">
                {part.promptIndex === 0 ? 'Positive Prompt' : 'Negative Prompt'}
              </span>
              <div class="prompt-actions">
                {#if part.promptIndex === 0 && !isUser}
                  <button
                    class="gen-btn"
                    class:generating
                    disabled={generating || streaming}
                    on:click={generate}
                  >
                    {generating ? 'Generating…' : 'Generate'}
                  </button>
                {/if}
                <button
                  class="copy-btn"
                  class:copied={copiedIndex === i}
                  on:click={() => copy(part.content, i)}
                >
                  {copiedIndex === i ? '✓ Copied' : 'Copy'}
                </button>
              </div>
            </div>
            <pre class="prompt-text">{part.content}</pre>
          </div>
        {/if}
      {/each}

      {#if generating}
        <div class="gen-status">
          <span class="gen-spinner">◌</span>
          <span>Queued in ComfyUI — waiting for output…</span>
        </div>
      {/if}

      {#if genError}
        <div class="gen-error">{genError}</div>
      {/if}

      {#if generatedImage}
        <div class="gen-result">
          <img src={generatedImage.src} alt="Generated" class="gen-image" />
          <div class="gen-meta">
            {#if generatedImage.seed != null}seed {generatedImage.seed}{/if}
            {#if generatedImage.checkpoint} · {generatedImage.checkpoint}{/if}
          </div>
        </div>
      {/if}

      {#if streaming}<span class="cursor">▋</span>{/if}
    </div>
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

  .user .bubble  { align-items: flex-end; }
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
    width: 100%;
    box-sizing: border-box;
  }

  .content.has-prompt {
    padding: 10px 10px;
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

  .text-segment {
    white-space: pre-wrap;
  }

  /* ── Prompt block ── */
  .prompt-block {
    margin: 8px 0;
    border: 1px solid var(--accent);
    border-radius: 6px;
    overflow: hidden;
    background: var(--bg);
  }

  .prompt-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    background: color-mix(in srgb, var(--accent) 12%, var(--surface));
    border-bottom: 1px solid var(--accent);
  }

  .prompt-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--accent);
  }

  .prompt-actions {
    display: flex;
    gap: 6px;
    align-items: center;
  }

  .copy-btn {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 10px;
    border-radius: 4px;
    border: 1px solid var(--accent);
    background: transparent;
    color: var(--accent);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
    min-width: 58px;
  }
  .copy-btn:hover    { background: var(--accent); color: var(--bg); }
  .copy-btn.copied   { background: var(--status-ready); border-color: var(--status-ready); color: var(--bg); }

  .gen-btn {
    font-size: 11px;
    font-weight: 600;
    padding: 2px 12px;
    border-radius: 4px;
    border: 1px solid var(--status-ready);
    background: transparent;
    color: var(--status-ready);
    cursor: pointer;
    transition: background 0.12s, color 0.12s, opacity 0.12s;
  }
  .gen-btn:hover:not(:disabled)  { background: var(--status-ready); color: var(--bg); }
  .gen-btn:disabled               { opacity: 0.45; cursor: default; }
  .gen-btn.generating             { opacity: 0.6; }

  .prompt-text {
    margin: 0;
    padding: 10px 12px;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.6;
    color: var(--text);
    white-space: pre-wrap;
    word-break: break-word;
    background: transparent;
  }

  /* ── Generation status / result ── */
  .gen-status {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    font-size: 12px;
    color: var(--text-dim);
    font-family: var(--font-mono);
  }

  .gen-spinner {
    animation: spin 1.2s linear infinite;
    display: inline-block;
  }

  .gen-error {
    margin-top: 10px;
    font-size: 12px;
    color: var(--status-error);
    font-family: var(--font-mono);
  }

  .gen-result {
    margin-top: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .gen-image {
    max-width: 100%;
    border-radius: 6px;
    border: 1px solid var(--border);
    display: block;
  }

  .gen-meta {
    font-size: 10px;
    color: var(--text-dim);
    font-family: var(--font-mono);
  }

  /* ── Streaming cursor ── */
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

  @keyframes spin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
  }
</style>
