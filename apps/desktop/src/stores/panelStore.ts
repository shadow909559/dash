import { create } from "zustand";

export type PanelKind =
  | "research"
  | "system"
  | "coding"
  | "files"
  | "browser"
  | "tasks"
  | "memory"
  | "tools"
  | "notifications";

export interface PanelInstance {
  id: string;
  kind: PanelKind;
  title: string;
  x: number;
  y: number;
  width: number;
  height: number;
  minimized: boolean;
  zIndex: number;
  payload?: Record<string, unknown>;
}

interface PanelState {
  panels: PanelInstance[];
  maxZ: number;
  openPanel: (kind: PanelKind, title: string, payload?: Record<string, unknown>) => string;
  closePanel: (id: string) => void;
  closeKind: (kind: PanelKind) => void;
  updatePanel: (id: string, patch: Partial<PanelInstance>) => void;
  focusPanel: (id: string) => void;
  minimizePanel: (id: string) => void;
}

const DEFAULTS: Record<PanelKind, { width: number; height: number; x: number; y: number }> = {
  research: { width: 420, height: 480, x: 64, y: 96 },
  system: { width: 360, height: 420, x: 80, y: 110 },
  coding: { width: 480, height: 440, x: 120, y: 90 },
  files: { width: 440, height: 460, x: 100, y: 100 },
  browser: { width: 480, height: 460, x: 140, y: 80 },
  tasks: { width: 380, height: 400, x: 90, y: 120 },
  memory: { width: 380, height: 420, x: 110, y: 110 },
  tools: { width: 400, height: 380, x: 130, y: 130 },
  notifications: { width: 340, height: 360, x: 160, y: 90 },
};

function loadPositions(): Record<string, { x: number; y: number; width: number; height: number }> {
  try {
    return JSON.parse(localStorage.getItem("dash.panel.positions") || "{}");
  } catch {
    return {};
  }
}

function savePosition(kind: PanelKind, pos: { x: number; y: number; width: number; height: number }) {
  try {
    const all = loadPositions();
    all[kind] = pos;
    localStorage.setItem("dash.panel.positions", JSON.stringify(all));
  } catch {
    /* ignore */
  }
}

export const usePanelStore = create<PanelState>((set, get) => ({
  panels: [],
  maxZ: 40,
  openPanel: (kind, title, payload) => {
    const existing = get().panels.find((p) => p.kind === kind);
    if (existing) {
      get().focusPanel(existing.id);
      if (payload) get().updatePanel(existing.id, { payload: { ...existing.payload, ...payload }, minimized: false });
      return existing.id;
    }
    const saved = loadPositions()[kind];
    const defaults = DEFAULTS[kind];
    const z = get().maxZ + 1;
    const id = `panel_${kind}_${Date.now()}`;
    const panel: PanelInstance = {
      id,
      kind,
      title,
      x: saved?.x ?? defaults.x,
      y: saved?.y ?? defaults.y,
      width: saved?.width ?? defaults.width,
      height: saved?.height ?? defaults.height,
      minimized: false,
      zIndex: z,
      payload,
    };
    set({ panels: [...get().panels, panel], maxZ: z });
    return id;
  },
  closePanel: (id) => set({ panels: get().panels.filter((p) => p.id !== id) }),
  closeKind: (kind) => set({ panels: get().panels.filter((p) => p.kind !== kind) }),
  updatePanel: (id, patch) => {
    set({
      panels: get().panels.map((p) => {
        if (p.id !== id) return p;
        const next = { ...p, ...patch };
        savePosition(next.kind, { x: next.x, y: next.y, width: next.width, height: next.height });
        return next;
      }),
    });
  },
  focusPanel: (id) => {
    const z = get().maxZ + 1;
    set({
      maxZ: z,
      panels: get().panels.map((p) => (p.id === id ? { ...p, zIndex: z, minimized: false } : p)),
    });
  },
  minimizePanel: (id) =>
    set({
      panels: get().panels.map((p) => (p.id === id ? { ...p, minimized: !p.minimized } : p)),
    }),
}));
