import { create } from "zustand";
import { authFetch } from "@/lib/api";
import type { OrbState } from "@/three/aistates";
import type { DASHState } from "@/stores/dashState";
import { mapLegacyState, mapLegacyOrbState } from "@/stores/dashState";

type AIState = "idle" | "listening" | "thinking" | "researching" | "talking" | "processing" | "waiting" | "sleeping" | "reacting";

/** Small status-pill state (top-right). Distinct from the full AIState. */
export type AICoreStatus = "idle" | "thinking" | "listening" | "speaking" | "executing" | "error" | "provider_checking" | "provider_starting" | "provider_unavailable";

// Separate status tracking for all systems
export type SystemStatus = "offline" | "online";
export type AIProviderStatus = "offline" | "ready" | "listening" | "thinking" | "responding" | "error";
export type WebSocketStatus = "disconnected" | "connecting" | "connected" | "reconnecting";
export type ChatStatus = "idle" | "processing" | "error";
export type VoiceStatus = "offline" | "ready" | "listening" | "speaking" | "error";

interface SystemStats {
  cpu: number;
  gpu: number;
  ram: number;
  battery: number;
  batteryAvailable: boolean;
  storage: number;
  disk: number;
  network: number;
  bytesSent: number;
  bytesRecv: number;
  uptime: number;
  backend: boolean;
}

type Emotion = 
  | "neutral" 
  | "happy" 
  | "curious" 
  | "focused" 
  | "surprised" 
  | "concerned"
  | "excited"
  | "confused"
  | "calm"
  | "thinking"
  | "speaking"
  | "listening";

interface EmotionVisuals {
  color: string;
  glowIntensity: number;
  particleSpeed: number;
  breathingSpeed: number;
  pulseIntensity: number;
  waveAmplitude: number;
}

interface InfoCard {
  id: string;
  title: string;
  content: string;
  icon?: string;
  type: "weather" | "timer" | "email" | "calendar" | "reminder" | "music" | "volume" | "maps" | "battery" | "notification" | "clipboard" | "search" | "info" | "error" | "success";
}

export interface AIStore {
  aiState: AIState;
  setAIState: (state: AIState) => void;
  /** Small top-right status pill state. */
  coreStatus: AICoreStatus;
  setCoreStatus: (status: AICoreStatus) => void;
  
  // Separate system statuses
  systemStatus: SystemStatus;
  setSystemStatus: (status: SystemStatus) => void;
  
  aiProviderStatus: AIProviderStatus;
  setAIProviderStatus: (status: AIProviderStatus) => void;
  
  websocketStatus: WebSocketStatus;
  setWebSocketStatus: (status: WebSocketStatus) => void;
  
  chatStatus: ChatStatus;
  setChatStatus: (status: ChatStatus) => void;
  
  voiceStatus: VoiceStatus;
  setVoiceStatus: (status: VoiceStatus) => void;
  
  emotion: Emotion;
  setEmotion: (emotion: Emotion) => void;
  /** Direct orb mode override — maps 1:1 to the orb's 9 visual states. */
  orbMode: OrbState;
  setOrbMode: (mode: OrbState) => void;
  /** Window mode: full, floating, or orb */
  windowMode: "full" | "floating" | "orb";
  setWindowMode: (mode: "full" | "floating" | "orb") => void;
  /** DASH 2.0 centralized state */
  dashState: DASHState;
  setDashState: (state: DASHState) => void;
  lastMessage: string;
  setLastMessage: (message: string) => void;
  currentReply: string;
  setCurrentReply: (reply: string) => void;
  currentSpeech: string;
  setCurrentSpeech: (speech: string) => void;
  systemStats: SystemStats | null;
  setSystemStats: (stats: SystemStats) => void;
  cards: InfoCard[];
  addCard: (title: string, content: string, type: InfoCard["type"], icon?: string) => void;
  removeCard: (id: string) => void;
  getEmotionVisuals: (emotion: Emotion) => EmotionVisuals;
}

const emotionVisuals: Record<Emotion, EmotionVisuals> = {
  neutral: {
    color: "rgba(96, 165, 250, 0.3)",
    glowIntensity: 0.25,
    particleSpeed: 0.3,
    breathingSpeed: 1.0,
    pulseIntensity: 0.1,
    waveAmplitude: 0.05,
  },
  happy: {
    color: "rgba(74, 222, 128, 0.4)",
    glowIntensity: 0.4,
    particleSpeed: 0.5,
    breathingSpeed: 0.8,
    pulseIntensity: 0.2,
    waveAmplitude: 0.1,
  },
  curious: {
    color: "rgba(96, 165, 250, 0.4)",
    glowIntensity: 0.35,
    particleSpeed: 0.4,
    breathingSpeed: 0.9,
    pulseIntensity: 0.15,
    waveAmplitude: 0.08,
  },
  focused: {
    color: "rgba(167, 139, 250, 0.4)",
    glowIntensity: 0.5,
    particleSpeed: 0.2,
    breathingSpeed: 1.2,
    pulseIntensity: 0.1,
    waveAmplitude: 0.03,
  },
  surprised: {
    color: "rgba(251, 191, 36, 0.4)",
    glowIntensity: 0.45,
    particleSpeed: 0.6,
    breathingSpeed: 0.7,
    pulseIntensity: 0.25,
    waveAmplitude: 0.15,
  },
  concerned: {
    color: "rgba(248, 113, 113, 0.4)",
    glowIntensity: 0.35,
    particleSpeed: 0.25,
    breathingSpeed: 1.1,
    pulseIntensity: 0.12,
    waveAmplitude: 0.06,
  },
  excited: {
    color: "rgba(236, 72, 153, 0.45)",
    glowIntensity: 0.5,
    particleSpeed: 0.7,
    breathingSpeed: 0.6,
    pulseIntensity: 0.3,
    waveAmplitude: 0.2,
  },
  confused: {
    color: "rgba(167, 139, 250, 0.35)",
    glowIntensity: 0.3,
    particleSpeed: 0.35,
    breathingSpeed: 1.0,
    pulseIntensity: 0.15,
    waveAmplitude: 0.07,
  },
  calm: {
    color: "rgba(96, 165, 250, 0.25)",
    glowIntensity: 0.2,
    particleSpeed: 0.2,
    breathingSpeed: 1.5,
    pulseIntensity: 0.08,
    waveAmplitude: 0.03,
  },
  thinking: {
    color: "rgba(167, 139, 250, 0.5)",
    glowIntensity: 0.4,
    particleSpeed: 0.4,
    breathingSpeed: 1.0,
    pulseIntensity: 0.15,
    waveAmplitude: 0.05,
  },
  speaking: {
    color: "rgba(74, 222, 128, 0.45)",
    glowIntensity: 0.5,
    particleSpeed: 0.6,
    breathingSpeed: 0.7,
    pulseIntensity: 0.25,
    waveAmplitude: 0.12,
  },
  listening: {
    color: "rgba(96, 165, 250, 0.5)",
    glowIntensity: 0.5,
    particleSpeed: 0.5,
    breathingSpeed: 0.8,
    pulseIntensity: 0.2,
    waveAmplitude: 0.1,
  },
};

export const useAIStore = create<AIStore>((set, get) => ({
  aiState: "idle",
  setAIState: (state) => {
    set({ aiState: state });
    // Auto-update DASH state when AI state changes
    set({ dashState: mapLegacyState(state) });
  },
  coreStatus: "idle",
  setCoreStatus: (status) => set({ coreStatus: status }),
  
  // Initialize separate system statuses
  systemStatus: "online",
  setSystemStatus: (status) => set({ systemStatus: status }),
  
  aiProviderStatus: "ready",
  setAIProviderStatus: (status) => set({ aiProviderStatus: status }),
  
  websocketStatus: "disconnected",
  setWebSocketStatus: (status) => set({ websocketStatus: status }),
  
  chatStatus: "idle",
  setChatStatus: (status) => set({ chatStatus: status }),
  
  voiceStatus: "offline",
  setVoiceStatus: (status) => set({ voiceStatus: status }),
  
  emotion: "neutral",
  setEmotion: (emotion) => set({ emotion }),
  orbMode: "standby",
  setOrbMode: (mode) => {
    set({ orbMode: mode });
    // Auto-update DASH state when orb mode changes
    set({ dashState: mapLegacyOrbState(mode) });
  },
  windowMode: "full",
  setWindowMode: (mode) => set({ windowMode: mode }),
  dashState: "idle",
  setDashState: (state) => set({ dashState: state }),
  lastMessage: "",
  setLastMessage: (message) => set({ lastMessage: message }),
  currentReply: "",
  setCurrentReply: (reply) => set({ currentReply: reply }),
  currentSpeech: "",
  setCurrentSpeech: (speech) => set({ currentSpeech: speech }),
  systemStats: null,
  setSystemStats: (stats) => set({ systemStats: stats }),
  cards: [],
  addCard: (title, content, type, icon) => {
    const id = Date.now().toString() + Math.random().toString(36).slice(2);
    set((state) => ({ cards: [...state.cards, { id, title, content, type, icon }] }));
  },
  removeCard: (id) => set((state) => ({ cards: state.cards.filter((c) => c.id !== id) })),
  getEmotionVisuals: (emotion) => emotionVisuals[emotion] || emotionVisuals.neutral,
}));

// System stats polling - moved to component with proper cleanup to prevent memory leaks
// The backend exposes real resources under /monitor/health
// (resources.{cpu,memory,disk,gpu,network} and components.backend.uptime).
export const SYSTEM_STATS_URL = `${import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1"}/monitor/health`;

export const startSystemStatsPolling = (intervalMs: number = 5000) => {
  if (typeof window === 'undefined') return null;

  const intervalId = setInterval(async () => {
    try {
      const response = await authFetch(SYSTEM_STATS_URL);
      if (!response.ok) return;
      const health = await response.json();
      const res = health?.resources || {};
      const backend = health?.components?.backend || {};
      const gpu = res.gpu || {};
      const disk = res.disk || {};
      const net = res.network || {};
      const batt = res.battery || {};
      useAIStore.getState().setSystemStats({
        cpu: res.cpu?.percent ?? 0,
        gpu: gpu.percent ?? 0,
        ram: res.memory?.percent ?? 0,
        battery: batt.percent ?? 0,
        batteryAvailable: Boolean(batt.available),
        storage: disk.percent ?? 0,
        disk: disk.percent ?? 0,
        network: net.bytes_recv ? 1 : 0,
        bytesSent: net.bytes_sent ?? 0,
        bytesRecv: net.bytes_recv ?? 0,
        uptime: backend.uptime ?? 0,
        backend: health?.status === "ok",
      });
      useAIStore.getState().setSystemStatus(health?.status === "ok" ? "online" : "offline");
    } catch (e) {
      // No data yet — do not fabricate. The dashboard simply waits.
      console.warn("[aiStore] system stats unavailable", e);
    }
  }, intervalMs);

  return intervalId;
}