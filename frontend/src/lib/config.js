const CONFIG_KEY = 'ai_harness_config';

// Hardcoded — shared secret between frontend and all module endpoints.
// To rotate: update this value and HARNESS_API_KEY in each module's .env.
export const API_KEY = 'sf71D2G5#$841#axf55F1';

const BUILTIN_PROFILES = [
  {
    id: 'local',
    label: 'Local Ollama',
    moduleUrl: 'http://127.0.0.1:8080',
    description: 'harness_module on this machine → Ollama at localhost:11434',
  },
  {
    id: 'runpod',
    label: 'RunPod',
    moduleUrl: '',
    description: 'harness_module running on a RunPod GPU pod',
  },
];

const DEFAULTS = {
  activeProfileId: 'local',
  profiles: BUILTIN_PROFILES,
  activeCharacter: 'pip',
};

export { BUILTIN_PROFILES };

export function loadConfig() {
  try {
    const raw = localStorage.getItem(CONFIG_KEY);
    if (!raw) return structuredClone(DEFAULTS);
    const saved = JSON.parse(raw);
    const profileMap = Object.fromEntries((saved.profiles ?? []).map(p => [p.id, p]));
    for (const bp of BUILTIN_PROFILES) {
      if (!profileMap[bp.id]) profileMap[bp.id] = { ...bp };
    }
    return {
      ...DEFAULTS,
      ...saved,
      profiles: Object.values(profileMap),
    };
  } catch {
    return structuredClone(DEFAULTS);
  }
}

export function saveConfig(cfg) {
  localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
}

export function activeProfile(cfg) {
  return cfg.profiles?.find(p => p.id === cfg.activeProfileId) ?? cfg.profiles?.[0] ?? null;
}

export function isConfigured(cfg) {
  return !!activeProfile(cfg)?.moduleUrl?.trim();
}
