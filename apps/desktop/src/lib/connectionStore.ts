import { create } from "zustand";

interface ConnectionState {
  isConnected: boolean;
  backendUrl: string;
  setConnected: (v: boolean) => void;
  setBackendUrl: (url: string) => void;
  checkBackend: () => Promise<void>;
}

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  isConnected: false,
  backendUrl: "http://localhost:8000",

  setConnected: (v) => set({ isConnected: v }),
  setBackendUrl: (url) => set({ backendUrl: url }),

  checkBackend: async () => {
    try {
      const resp = await fetch(`${get().backendUrl}/health`, {
        method: "GET",
        signal: AbortSignal.timeout(5000),
      });
      set({ isConnected: resp.ok });
    } catch {
      set({ isConnected: false });
    }
  },
}));
