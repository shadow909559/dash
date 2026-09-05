import { create } from "zustand";

export interface ActivityItem {
  id: string;
  time: string;
  message: string;
  kind: "system" | "ai" | "chat" | "tool" | "voice" | "error";
}

interface ActivityState {
  items: ActivityItem[];
  push: (message: string, kind?: ActivityItem["kind"]) => void;
}

function stamp(): string {
  const d = new Date();
  return d.toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit" });
}

export const useActivityStore = create<ActivityState>((set, get) => ({
  items: [],
  push: (message, kind = "system") => {
    const last = get().items[0];
    if (last && last.message === message) return;
    const item: ActivityItem = {
      id: `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
      time: stamp(),
      message,
      kind,
    };
    set({ items: [item, ...get().items].slice(0, 40) });
  },
}));
