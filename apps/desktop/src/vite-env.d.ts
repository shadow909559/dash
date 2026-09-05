/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WS_URL?: string;
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

interface ElectronAPI {
  auth?: {
    deviceToken: () => Promise<{ ok: boolean; token?: string; reason?: string }>;
  };
  window?: {
    minimize: () => Promise<{ ok: boolean }>;
    maximize: () => Promise<{ ok: boolean }>;
    close: () => Promise<{ ok: boolean }>;
    isMaximized: () => Promise<boolean>;
    setMode?: (mode: "full" | "floating" | "orb") => Promise<{ ok: boolean }>;
    getMode?: () => Promise<string>;
    onMaximizeChange?: (callback: (maximized: boolean) => void) => () => void;
  };
  onAudioStopAll?: (callback: () => void) => () => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
