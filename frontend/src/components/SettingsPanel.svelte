<script>
  import { config, showSettings, moduleUrl } from '../lib/stores.js';
  import { saveConfig, activeProfile } from '../lib/config.js';
  import { API_KEY } from '../lib/config.js';
  import { get } from 'svelte/store';

  let cfg = { ...$config, profiles: $config.profiles.map(p => ({ ...p })) };
  let testResult = '';
  let testing = false;
  let updating = false;
  let updateResult = '';

  $: currentProfile = cfg.profiles.find(p => p.id === cfg.activeProfileId) ?? cfg.profiles[0];

  function selectProfile(id) {
    cfg.activeProfileId = id;
    cfg = cfg;
  }

  function addProfile() {
    const id = 'custom_' + Date.now();
    cfg.profiles = [...cfg.profiles, { id, label: 'New Endpoint', moduleUrl: '', description: '' }];
    cfg.activeProfileId = id;
  }

  function removeProfile(id) {
    cfg.profiles = cfg.profiles.filter(p => p.id !== id);
    if (cfg.activeProfileId === id) cfg.activeProfileId = cfg.profiles[0]?.id ?? '';
    cfg = cfg;
  }

  function handleSave() {
    config.set(cfg);
    saveConfig(cfg);
    showSettings.set(false);
  }

  async function handleTest() {
    testing = true;
    testResult = '';
    try {
      const url = currentProfile?.moduleUrl?.replace(/\/$/, '');
      if (!url) { testResult = '✗ No URL set for this profile'; testing = false; return; }
      const res = await fetch(`${url}/health`);
      const data = await res.json();
      testResult = `✓ Reachable — status: ${data.status ?? 'unknown'}`;
    } catch (e) {
      testResult = `✗ Unreachable: ${e.message}`;
    } finally {
      testing = false;
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') showSettings.set(false);
  }

  $: isRunPod = cfg.activeProfileId === 'runpod';

  async function handleUpdate() {
    updating = true;
    updateResult = '';
    try {
      const url = get(moduleUrl).replace(/\/$/, '');
      const res = await fetch(`${url}/v1/admin/update`, {
        method: 'POST',
        headers: { 'X-API-Key': API_KEY },
      });
      const data = await res.json();
      updateResult = res.ok ? '✓ Update triggered — pod will restart shortly' : `✗ ${data.detail ?? 'Unknown error'}`;
    } catch (e) {
      updateResult = `✗ ${e.message}`;
    } finally {
      updating = false;
    }
  }

  const BUILTIN = new Set(['local', 'runpod']);
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="backdrop" on:click={() => showSettings.set(false)} role="presentation"></div>

<div class="panel" role="dialog" aria-label="Settings">
  <div class="panel-header">
    <h2>Connection Settings</h2>
    <button class="close-btn" on:click={() => showSettings.set(false)}>✕</button>
  </div>

  <div class="panel-body">
    <div class="section-label">Routing Target</div>
    <div class="profile-list">
      {#each cfg.profiles as profile (profile.id)}
        <button
          class="profile-row"
          class:active={cfg.activeProfileId === profile.id}
          on:click={() => selectProfile(profile.id)}
        >
          <div class="profile-info">
            <span class="profile-label">{profile.label}</span>
            <span class="profile-url">{profile.moduleUrl || '(no URL set)'}</span>
          </div>
          {#if !BUILTIN.has(profile.id)}
            <button class="remove-btn" on:click|stopPropagation={() => removeProfile(profile.id)} title="Remove">✕</button>
          {/if}
        </button>
      {/each}
      <button class="add-profile-btn" on:click={addProfile}>+ Add endpoint</button>
    </div>

    {#if currentProfile}
      <div class="profile-editor">
        <div class="field">
          <label for="profile-label">Label</label>
          <input id="profile-label" type="text" bind:value={currentProfile.label} />
        </div>
        <div class="field">
          <label for="profile-url">Module URL</label>
          <input
            id="profile-url"
            type="url"
            bind:value={currentProfile.moduleUrl}
            placeholder="http://127.0.0.1:8080  or  https://xxxx-8080.proxy.runpod.net"
            spellcheck="false"
          />
          {#if currentProfile.id === 'local'}
            <div class="hint">Points to harness_module on this machine → Ollama at localhost:11434</div>
          {:else if currentProfile.id === 'runpod'}
            <div class="hint">Use the RunPod "Connect" tab URL with port 8080 exposed.</div>
          {/if}
        </div>
      </div>
    {/if}

    <div class="divider"></div>

    <div class="field">
      <label for="character">Active Character</label>
      <select id="character" bind:value={cfg.activeCharacter}>
        <option value="pip">Pip (Companion)</option>
        <option value="code_agent">Code Agent (Engineering)</option>
        <option value="media_agent">Media Agent (Visual Gen)</option>
        <option value="mental_health">Reflect (Wellbeing)</option>
      </select>
    </div>

    {#if isRunPod}
      <div class="divider"></div>
      <div class="section-label">Pod Management</div>
      <div class="update-row">
        <div class="update-info">
          <span class="update-label">Update Pod</span>
          <span class="update-hint">Pull latest code from GitHub and restart</span>
        </div>
        <button class="btn-secondary" on:click={handleUpdate} disabled={updating}>
          {updating ? 'Updating…' : 'Update'}
        </button>
      </div>
      {#if updateResult}
        <div class="test-result" class:ok={updateResult.startsWith('✓')}>{updateResult}</div>
      {/if}
    {/if}
  </div>

  <div class="panel-footer">
    {#if testResult}
      <div class="test-result" class:ok={testResult.startsWith('✓')}>{testResult}</div>
    {/if}
    <div class="actions">
      <button class="btn-secondary" on:click={handleTest} disabled={testing}>
        {testing ? 'Testing…' : 'Test Connection'}
      </button>
      <button class="btn-primary" on:click={handleSave}>Save</button>
    </div>
  </div>
</div>

<style>
  .backdrop {
    position: fixed; inset: 0;
    background: rgba(0,0,0,0.6);
    z-index: 100;
    backdrop-filter: blur(2px);
  }

  .panel {
    position: fixed;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    z-index: 101;
    width: 500px;
    max-height: 85vh;
    overflow-y: auto;
    background: var(--surface);
    border: 1px solid var(--border-bright);
    border-radius: 10px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 24px 64px rgba(0,0,0,0.6);
    animation: fadeIn 0.15s ease;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 18px 20px 14px;
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0;
    background: var(--surface);
    z-index: 1;
  }

  h2 { font-size: 15px; font-weight: 600; }

  .close-btn {
    color: var(--text-muted);
    font-size: 14px;
    padding: 4px 6px;
    border-radius: 4px;
    transition: color 0.15s;
  }
  .close-btn:hover { color: var(--text); }

  .panel-body {
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .section-label {
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--text-dim);
  }

  .profile-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .profile-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 10px;
    border-radius: var(--radius);
    border: 1px solid transparent;
    text-align: left;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
    width: 100%;
  }
  .profile-row:hover { background: var(--surface-2); }
  .profile-row.active { background: var(--accent-dim); border-color: var(--accent); }

  .profile-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
    overflow: hidden;
    min-width: 0;
  }

  .profile-label { font-size: 13px; font-weight: 500; color: var(--text); }
  .profile-row.active .profile-label { color: var(--accent); }

  .profile-url {
    font-size: 11px;
    color: var(--text-dim);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .remove-btn {
    color: var(--text-dim);
    font-size: 12px;
    padding: 2px 5px;
    border-radius: 3px;
    flex-shrink: 0;
    margin-left: 8px;
  }
  .remove-btn:hover { color: var(--status-error); }

  .add-profile-btn {
    font-size: 12px;
    color: var(--text-dim);
    padding: 6px 10px;
    border-radius: var(--radius);
    border: 1px dashed var(--border);
    text-align: left;
    transition: color 0.15s, border-color 0.15s;
  }
  .add-profile-btn:hover { color: var(--accent); border-color: var(--accent); }

  .profile-editor {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
  }

  .divider { height: 1px; background: var(--border); }

  .field { display: flex; flex-direction: column; gap: 6px; }

  label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }

  .hint { font-size: 11px; color: var(--text-dim); }

  .panel-footer {
    padding: 14px 20px 18px;
    border-top: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 12px;
    position: sticky; bottom: 0;
    background: var(--surface);
  }

  .test-result {
    font-size: 12px;
    color: var(--status-error);
    font-family: var(--font-mono);
  }
  .test-result.ok { color: var(--status-ready); }

  .actions { display: flex; gap: 8px; justify-content: flex-end; }

  .btn-primary {
    background: var(--accent);
    color: var(--bg);
    border-radius: var(--radius);
    padding: 8px 20px;
    font-weight: 600;
    font-size: 13px;
    transition: opacity 0.15s;
  }
  .btn-primary:hover { opacity: 0.85; }

  .btn-secondary {
    background: var(--surface-3);
    border: 1px solid var(--border);
    color: var(--text-muted);
    border-radius: var(--radius);
    padding: 8px 16px;
    font-size: 13px;
    transition: border-color 0.15s, color 0.15s;
  }
  .btn-secondary:hover:not(:disabled) { border-color: var(--accent); color: var(--text); }
  .btn-secondary:disabled { opacity: 0.4; cursor: default; }

  .update-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .update-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .update-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
  }

  .update-hint {
    font-size: 11px;
    color: var(--text-dim);
  }
</style>
