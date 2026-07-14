import { create } from 'zustand';
import { DEFAULT_BACKEND_URL, DEFAULT_WS_URL } from '../agent/agentTypes';

// ── Persistence key ──────────────────────────────────────────────────────
const STORAGE_KEY = 'dash-settings';

// ── URL Validation ───────────────────────────────────────────────────────
export type ValidationResult =
  | { valid: true }
  | { valid: false; error: string };

export function validateHttpUrl(url: string): ValidationResult {
  if (!url) return { valid: false, error: 'URL is required' };
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return { valid: false, error: 'URL must start with http:// or https://' };
    }
    if (!parsed.hostname) {
      return { valid: false, error: 'URL must include a hostname' };
    }
    return { valid: true };
  } catch {
    return { valid: false, error: 'Invalid URL format' };
  }
}

export function validateWsUrl(url: string): ValidationResult {
  if (!url) return { valid: false, error: 'WebSocket URL is required' };
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'ws:' && parsed.protocol !== 'wss:') {
      return { valid: false, error: 'URL must start with ws:// or wss://' };
    }
    if (!parsed.hostname) {
      return { valid: false, error: 'URL must include a hostname' };
    }
    return { valid: true };
  } catch {
    return { valid: false, error: 'Invalid URL format' };
  }
}

// ── Types ────────────────────────────────────────────────────────────────
export type SettingsSectionKey =
  | 'general'
  | 'agent'
  | 'aiProviders'
  | 'voice'
  | 'memory'
  | 'automation'
  | 'notifications'
  | 'appearance'
  | 'about';

export type SettingsState = {
  general: {
    autoScroll: boolean;
    showMarkdown: boolean;
    backendUrl: string;
    wsUrl: string;
  };
  aiProviders: {
    provider: 'openai' | 'ollama' | 'other';
    model: string;
    apiKey: string;
  };
  voice: {
    voiceEnabled: boolean;
    ttsVolume: number; // 0-100
    sttSensitivity: number; // 0-100
  };
  memory: {
    enabled: boolean;
    maxItems: number;
  };
  automation: {
    enabled: boolean;
  };
  notifications: {
    enabled: boolean;
    desktopOnly: boolean;
  };
  appearance: {
    theme: 'dark' | 'light' | 'system';
    accentColor: string;
  };
};

type SettingsActions = {
  setGeneral: (patch: Partial<SettingsState['general']>) => void;
  setAiProviders: (patch: Partial<SettingsState['aiProviders']>) => void;
  setVoice: (patch: Partial<SettingsState['voice']>) => void;
  setMemory: (patch: Partial<SettingsState['memory']>) => void;
  setAutomation: (patch: Partial<SettingsState['automation']>) => void;
  setNotifications: (patch: Partial<SettingsState['notifications']>) => void;
  setAppearance: (patch: Partial<SettingsState['appearance']>) => void;
  persist: () => void;
  loadPersisted: () => void;
};

// ── Defaults ─────────────────────────────────────────────────────────────
const DEFAULTS: SettingsState = {
  general: {
    autoScroll: true,
    showMarkdown: true,
    backendUrl: DEFAULT_BACKEND_URL,
    wsUrl: DEFAULT_WS_URL,
  },
  aiProviders: {
    provider: 'openai',
    model: 'gpt-4o-mini',
    apiKey: '',
  },
  voice: {
    voiceEnabled: true,
    ttsVolume: 70,
    sttSensitivity: 55,
  },
  memory: {
    enabled: true,
    maxItems: 500,
  },
  automation: {
    enabled: false,
  },
  notifications: {
    enabled: true,
    desktopOnly: true,
  },
  appearance: {
    theme: 'dark',
    accentColor: '#6ea8fe',
  },
};

function loadFromStorage(): Partial<SettingsState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Partial<SettingsState>;
  } catch {
    return {};
  }
}

function saveToStorage(state: SettingsState): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage may be full or unavailable
  }
}

// ── Store ────────────────────────────────────────────────────────────────
export const useSettingsStore = create<SettingsState & SettingsActions>((set, get) => ({
  ...DEFAULTS,
  ...loadFromStorage(),

  setGeneral: (patch) => {
    set((s) => ({ general: { ...s.general, ...patch } }));
    saveToStorage({ ...get(), ...{ general: { ...get().general, ...patch } } });
  },
  setAiProviders: (patch) => {
    set((s) => ({ aiProviders: { ...s.aiProviders, ...patch } }));
    saveToStorage({ ...get(), ...{ aiProviders: { ...get().aiProviders, ...patch } } });
  },
  setVoice: (patch) => {
    set((s) => ({ voice: { ...s.voice, ...patch } }));
    saveToStorage({ ...get(), ...{ voice: { ...get().voice, ...patch } } });
  },
  setMemory: (patch) => {
    set((s) => ({ memory: { ...s.memory, ...patch } }));
    saveToStorage({ ...get(), ...{ memory: { ...get().memory, ...patch } } });
  },
  setAutomation: (patch) => {
    set((s) => ({ automation: { ...s.automation, ...patch } }));
    saveToStorage({ ...get(), ...{ automation: { ...get().automation, ...patch } } });
  },
  setNotifications: (patch) => {
    set((s) => ({ notifications: { ...s.notifications, ...patch } }));
    saveToStorage({ ...get(), ...{ notifications: { ...get().notifications, ...patch } } });
  },
  setAppearance: (patch) => {
    set((s) => ({ appearance: { ...s.appearance, ...patch } }));
    saveToStorage({ ...get(), ...{ appearance: { ...get().appearance, ...patch } } });
  },
  persist: () => saveToStorage(get()),
  loadPersisted: () => {
    const persisted = loadFromStorage();
    set((s) => ({
      general: { ...s.general, ...persisted.general },
      aiProviders: { ...s.aiProviders, ...persisted.aiProviders },
      voice: { ...s.voice, ...persisted.voice },
      memory: { ...s.memory, ...persisted.memory },
      automation: { ...s.automation, ...persisted.automation },
      notifications: { ...s.notifications, ...persisted.notifications },
      appearance: { ...s.appearance, ...persisted.appearance },
    }));
  },
}));

