<script>
  import { onMount, onDestroy } from 'svelte';
  import Sidebar       from './components/Sidebar.svelte';
  import ChatLog       from './components/ChatLog.svelte';
  import ChatInput     from './components/ChatInput.svelte';
  import SettingsPanel from './components/SettingsPanel.svelte';
  import SableModeBar  from './components/SableModeBar.svelte';

  import {
    config, moduleUrl, connectionState, connectionDetail,
    installProgress, statusData, availableModels,
    selectedModel, showSettings,
  } from './lib/stores.js';

  $: isSable = $config.activeCharacter === 'sable';
  import { checkHealth, listModels } from './lib/api.js';
  import { isConfigured, activeProfile, API_KEY } from './lib/config.js';

  let pollTimer = null;

  // Polling intervals
  const POLL_FAST = 5000;   // while not ready
  const POLL_SLOW = 20000;  // while ready

  async function poll() {
    const cfg = $config;

    if (!isConfigured(cfg)) {
      connectionState.set('unreachable');
      connectionDetail.set('Not configured — open Settings');
      scheduleNext(POLL_FAST);
      return;
    }

    const url = activeProfile(cfg)?.moduleUrl ?? '';
    const result = await checkHealth(url, API_KEY);

    connectionState.set(result.state);
    connectionDetail.set(result.detail ?? '');
    installProgress.set(result.progress ?? 0);

    if (result.statusData) {
      statusData.set(result.statusData);
    }

    // Refresh model list when connected
    if (['ready','no_model','backend_down'].includes(result.state) && result.statusData) {
      try {
        const ml = await listModels(url, API_KEY);
        availableModels.set(ml.models ?? []);
        // Pre-select loaded model
        if (ml.loaded && !$selectedModel) selectedModel.set(ml.loaded);
      } catch { /* ignore */ }
    }

    scheduleNext(result.state === 'ready' ? POLL_SLOW : POLL_FAST);
  }

  function scheduleNext(ms) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, ms);
  }

  function onModelLoaded() {
    // Immediately re-poll so status updates without waiting
    clearTimeout(pollTimer);
    poll();
  }

  onMount(() => {
    // Show settings if not configured
    if (!isConfigured($config)) showSettings.set(true);
    poll();
  });

  // Re-poll immediately when config changes
  $: if ($config) {
    clearTimeout(pollTimer);
    poll();
  }

  onDestroy(() => clearTimeout(pollTimer));
</script>

<div class="app-shell">
  <Sidebar {onModelLoaded} />

  <main class="main">
    {#if isSable}
      <SableModeBar {onModelLoaded} />
    {/if}
    <ChatLog />
    <ChatInput />
  </main>
</div>

{#if $showSettings}
  <SettingsPanel />
{/if}

<style>
  .app-shell {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background: var(--bg);
  }
</style>
