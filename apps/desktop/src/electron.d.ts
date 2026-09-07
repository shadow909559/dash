export interface ElectronAPI {
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
