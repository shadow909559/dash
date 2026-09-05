import { create } from "zustand";

// ── Types ──────────────────────────────────────────────────

export interface DashBubbleAction {
  label: string;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger";
}

export interface DashBubbleMetric {
  label: string;
  value: string | number;
  color?: string;
}

export interface DashBubbleFile {
  name: string;
  icon?: string;
  size?: string;
}

export interface DashBubble {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: number;
  ttl?: number;
  title?: string;
  text?: string;
  code?: string;
  image?: string;
  file?: DashBubbleFile;
  progress?: number;
  metrics?: DashBubbleMetric[];
  actions?: DashBubbleAction[];
  metadata?: Record<string, unknown>;
}

export type VoiceState =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "success"
  | "research"
  | "coding"
  | "error"
  | "serious"
  | "disconnected";

// ── Store ──────────────────────────────────────────────────

interface UIState {
  // Command palette
  commandPaletteOpen: boolean;
  setCommandPaletteOpen: (v: boolean) => void;

  // Settings
  isCommandPaletteOpen: boolean;
  isSettingsOpen: boolean;
  seriousMode: boolean;
  activePanel: string | null;
  toggleCommandPalette: () => void;
  toggleSettings: () => void;
  setSeriousMode: (v: boolean) => void;
  setActivePanel: (p: string | null) => void;

  // Bubbles (used by BubbleSystem + FloatingBubble)
  bubbles: DashBubble[];
  addBubble: (b: Omit<DashBubble, "id" | "createdAt">) => void;
  dismissBubble: (id: string) => void;
  clearBubbles: () => void;

  // Voice state (used by OrbEngine)
  voiceState: VoiceState;
  voiceAmplitude: number;
  orbAmplitude: number;
  setVoiceState: (v: VoiceState) => void;
  setVoiceAmplitude: (a: number) => void;
  setOrbAmplitude: (a: number) => void;
}

let _bubbleCounter = 0;

export const useUIStore = create<UIState>((set) => ({
  // Command palette
  commandPaletteOpen: false,
  setCommandPaletteOpen: (v) => set({ commandPaletteOpen: v }),

  // Settings
  isCommandPaletteOpen: false,
  isSettingsOpen: false,
  seriousMode: false,
  activePanel: null,
  toggleCommandPalette: () =>
    set((s) => ({
      commandPaletteOpen: !s.commandPaletteOpen,
      isCommandPaletteOpen: !s.isCommandPaletteOpen,
    })),
  toggleSettings: () => set((s) => ({ isSettingsOpen: !s.isSettingsOpen })),
  setSeriousMode: (v) => set({ seriousMode: v }),
  setActivePanel: (p) => set({ activePanel: p }),

  // Bubbles
  bubbles: [],
  addBubble: (b) =>
    set((s) => ({
      bubbles: [
        ...s.bubbles,
        {
          ...b,
          id: `bubble-${++_bubbleCounter}`,
          createdAt: Date.now(),
        },
      ],
    })),
  dismissBubble: (id) =>
    set((s) => ({
      bubbles: s.bubbles.filter((b) => b.id !== id),
    })),
  clearBubbles: () => set({ bubbles: [] }),

  // Voice
  voiceState: "idle",
  voiceAmplitude: 0,
  orbAmplitude: 0,
  setVoiceState: (v) => set({ voiceState: v }),
  setVoiceAmplitude: (a) => set({ voiceAmplitude: a }),
  setOrbAmplitude: (a) => set({ orbAmplitude: a }),
}));
