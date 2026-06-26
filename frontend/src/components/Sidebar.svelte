<script>
  import ConnectionStatus from './ConnectionStatus.svelte';
  import RoutingTarget    from './RoutingTarget.svelte';
  import ModelSelector    from './ModelSelector.svelte';
  import { config, showSettings, clearHistory, isStreaming } from '../lib/stores.js';
  import { saveConfig } from '../lib/config.js';

  export let onModelLoaded = () => {};

  const CHARACTERS = [
    { id: 'pip',           label: 'Pip',            sub: 'Companion' },
    { id: 'code_agent',    label: 'Code Agent',     sub: 'Engineering' },
    { id: 'media_agent',   label: 'Media Agent',    sub: 'Visual Gen' },
    { id: 'mental_health', label: 'Reflect',        sub: 'Wellbeing' },
  ];

  function selectCharacter(id) {
    config.update(c => {
      const updated = { ...c, activeCharacter: id };
      saveConfig(updated);
      return updated;
    });
    // History is preserved — switching agents just changes the active view
  }

  function openSettings() {
    showSettings.set(true);
  }

  function handleNewChat() {
    clearHistory($config.activeCharacter);
  }
</script>

<aside class="sidebar">
  <!-- Header -->
  <div class="sidebar-header">
    <span class="wordmark">AI Harness</span>
    <button class="icon-btn" on:click={openSettings} title="Settings">⚙</button>
  </div>

  <!-- Connection status -->
  <div class="sidebar-section">
    <ConnectionStatus />
  </div>

  <div class="divider"></div>

  <!-- Routing target -->
  <div class="sidebar-section">
    <RoutingTarget />
  </div>

  <div class="divider"></div>

  <!-- Model selector -->
  <div class="sidebar-section">
    <ModelSelector {onModelLoaded} />
  </div>

  <div class="divider"></div>

  <!-- Character selector -->
  <div class="sidebar-section">
    <div class="section-label">Character</div>
    <div class="character-list">
      {#each CHARACTERS as char}
        <button
          class="character-btn"
          class:active={$config.activeCharacter === char.id}
          on:click={() => selectCharacter(char.id)}
        >
          <span class="char-label">{char.label}</span>
          <span class="char-sub">{char.sub}</span>
        </button>
      {/each}
    </div>
  </div>

  <div class="spacer"></div>

  <!-- New chat -->
  <div class="sidebar-footer">
    <button
      class="new-chat-btn"
      on:click={handleNewChat}
      disabled={$isStreaming}
    >
      + New Chat
    </button>
  </div>
</aside>

<style>
  .sidebar {
    width: var(--sidebar-w);
    flex-shrink: 0;
    background: var(--surface);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
  }

  .sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 14px 14px;
    border-bottom: 1px solid var(--border);
  }

  .wordmark {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
  }

  .icon-btn {
    color: var(--text-dim);
    font-size: 16px;
    padding: 4px;
    border-radius: 4px;
    transition: color 0.15s;
    line-height: 1;
  }
  .icon-btn:hover { color: var(--text); }

  .sidebar-section {
    padding: 14px;
  }

  .divider {
    height: 1px;
    background: var(--border);
    margin: 0;
    flex-shrink: 0;
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
    margin-bottom: 8px;
  }

  .character-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .character-btn {
    width: 100%;
    text-align: left;
    padding: 8px 10px;
    border-radius: var(--radius);
    border: 1px solid transparent;
    display: flex;
    flex-direction: column;
    gap: 1px;
    transition: background 0.12s, border-color 0.12s;
  }
  .character-btn:hover {
    background: var(--surface-2);
  }
  .character-btn.active {
    background: var(--accent-dim);
    border-color: var(--accent);
  }

  .char-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
  }
  .character-btn.active .char-label { color: var(--accent); }

  .char-sub {
    font-size: 11px;
    color: var(--text-dim);
  }

  .spacer { flex: 1; }

  .sidebar-footer {
    padding: 12px 14px;
    border-top: 1px solid var(--border);
  }

  .new-chat-btn {
    width: 100%;
    padding: 8px;
    border-radius: var(--radius);
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    transition: border-color 0.15s, color 0.15s;
  }
  .new-chat-btn:hover:not(:disabled) { border-color: var(--accent); color: var(--text); }
  .new-chat-btn:disabled { opacity: 0.3; cursor: default; }
</style>
