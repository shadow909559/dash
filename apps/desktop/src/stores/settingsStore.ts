// Settings Store - Comprehensive application settings.

import { create } from "zustand";

export interface VoiceSettings {
  provider: "openai" | "azure" | "elevenlabs" | "piper" | "whisper";
  apiKey: string;
  voice: string;
  speed: number;
  pitch: number;
  language: string;
  personality: "friendly" | "professional" | "serious" | "funny" | "assistant" | "companion" | "developer" | "researcher";
}

export interface AISettings {
  model: string;
  temperature: number;
  maxTokens: number;
  systemPrompt: string;
  enableMemory: boolean;
  enablePlugins: boolean;
}

export interface PerformanceSettings {
  maxFPS: number;
  enableGPUAcceleration: boolean;
  particleCount: number;
  animationQuality: "low" | "medium" | "high" | "ultra";
  reduceMotion: boolean;
}

export interface ThemeSettings {
  theme: "dark" | "light" | "auto";
  accentColor: string;
  glassBlur: number;
  particleOpacity: number;
}

export interface PrivacySettings {
  enableTelemetry: boolean;
  enableCrashReports: boolean;
  localProcessingOnly: boolean;
  dataRetentionDays: number;
}

export interface PermissionSettings {
  microphone: boolean;
  camera: boolean;
  notifications: boolean;
  desktop: boolean;
  filesystem: boolean;
}

export interface ModelSettings {
  localModels: string[];
  cloudModels: string[];
  preferredModel: string;
  fallbackModel: string;
  modelCacheSize: number;
}

export interface UpdateSettings {
  autoUpdate: boolean;
  betaUpdates: boolean;
  updateChannel: "stable" | "beta" | "nightly";
  lastUpdateCheck: number;
}

export interface AccessibilitySettings {
  keyboardNavigation: boolean;
  screenReader: boolean;
  highContrast: boolean;
  fontSize: number;
  reducedMotion: boolean;
  focusVisible: boolean;
}

export interface Settings {
  voice: VoiceSettings;
  ai: AISettings;
  performance: PerformanceSettings;
  theme: ThemeSettings;
  privacy: PrivacySettings;
  permissions: PermissionSettings;
  models: ModelSettings;
  updates: UpdateSettings;
  accessibility: AccessibilitySettings;
}

interface SettingsActions {
  updateVoice: (settings: Partial<VoiceSettings>) => void;
  updateAI: (settings: Partial<AISettings>) => void;
  updatePerformance: (settings: Partial<PerformanceSettings>) => void;
  updateTheme: (settings: Partial<ThemeSettings>) => void;
  updatePrivacy: (settings: Partial<PrivacySettings>) => void;
  updatePermissions: (settings: Partial<PermissionSettings>) => void;
  updateModels: (settings: Partial<ModelSettings>) => void;
  updateUpdates: (settings: Partial<UpdateSettings>) => void;
  updateAccessibility: (settings: Partial<AccessibilitySettings>) => void;
  resetSettings: () => void;
}

const defaultSettings: Settings = {
  voice: {
    provider: "openai",
    apiKey: "",
    voice: "alloy",
    speed: 1.0,
    pitch: 1.0,
    language: "en",
    personality: "assistant",
  },
  ai: {
    model: "gpt-4",
    temperature: 0.7,
    maxTokens: 4096,
    systemPrompt: "You are DASH, an AI operating system assistant.",
    enableMemory: true,
    enablePlugins: true,
  },
  performance: {
    maxFPS: 120,
    enableGPUAcceleration: true,
    particleCount: 50,
    animationQuality: "high",
    reduceMotion: false,
  },
  theme: {
    theme: "dark",
    accentColor: "#60a5fa",
    glassBlur: 30,
    particleOpacity: 0.5,
  },
  privacy: {
    enableTelemetry: false,
    enableCrashReports: true,
    localProcessingOnly: false,
    dataRetentionDays: 30,
  },
  permissions: {
    microphone: true,
    camera: false,
    notifications: true,
    desktop: false,
    filesystem: false,
  },
  models: {
    localModels: [],
    cloudModels: ["gpt-4", "gpt-3.5-turbo", "claude-3-opus"],
    preferredModel: "gpt-4",
    fallbackModel: "gpt-3.5-turbo",
    modelCacheSize: 1024,
  },
  updates: {
    autoUpdate: true,
    betaUpdates: false,
    updateChannel: "stable",
    lastUpdateCheck: 0,
  },
  accessibility: {
    keyboardNavigation: true,
    screenReader: false,
    highContrast: false,
    fontSize: 16,
    reducedMotion: false,
    focusVisible: true,
  },
};

export const useSettingsStore = create<Settings & SettingsActions>((set) => ({
  ...defaultSettings,
  
  updateVoice: (settings) => set((state) => ({ voice: { ...state.voice, ...settings } })),
  updateAI: (settings) => set((state) => ({ ai: { ...state.ai, ...settings } })),
  updatePerformance: (settings) => set((state) => ({ performance: { ...state.performance, ...settings } })),
  updateTheme: (settings) => set((state) => ({ theme: { ...state.theme, ...settings } })),
  updatePrivacy: (settings) => set((state) => ({ privacy: { ...state.privacy, ...settings } })),
  updatePermissions: (settings) => set((state) => ({ permissions: { ...state.permissions, ...settings } })),
  updateModels: (settings) => set((state) => ({ models: { ...state.models, ...settings } })),
  updateUpdates: (settings) => set((state) => ({ updates: { ...state.updates, ...settings } })),
  updateAccessibility: (settings) => set((state) => ({ accessibility: { ...state.accessibility, ...settings } })),
  
  resetSettings: () => set(defaultSettings),
}));
