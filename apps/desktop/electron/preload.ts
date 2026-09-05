import { contextBridge, ipcRenderer } from "electron";

/** Shared listener handler factory to ensure consistent cleanup */
function createListener(event: string, callback: (...args: any[]) => void): () => void {
  const rendererEvent = `updater:${event}`;
  const handler = (_event: Electron.IpcRendererEvent, data: unknown) => {
    callback(data);
  };
  ipcRenderer.on(rendererEvent, handler);
  return () => {
    ipcRenderer.removeListener(rendererEvent, handler);
  };
}

// ────────────────────────────────────────────────────────────────────────────
// New electronAPI (recommended)
// ────────────────────────────────────────────────────────────────────────────
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  auth: {
    deviceToken: (): Promise<{ ok: boolean; token?: string; reason?: string }> =>
      ipcRenderer.invoke("auth:device-token"),
  },
  updater: {
    status: (): Promise<{
      checkInProgress: boolean;
      updateAvailable: boolean;
      updateDownloaded: boolean;
      version: string;
    }> => ipcRenderer.invoke("updater:status"),

    check: (): Promise<{ ok: boolean; reason?: string }> =>
      ipcRenderer.invoke("updater:check"),

    download: (): Promise<{ ok: boolean; reason?: string }> =>
      ipcRenderer.invoke("updater:download"),

    install: (): Promise<{ ok: boolean; reason?: string }> =>
      ipcRenderer.invoke("updater:install"),

    on: (event: string, callback: (...args: any[]) => void): (() => void) =>
      createListener(event, callback),

    off: (event: string, callback: (...args: any[]) => void): void => {
      const rendererEvent = `updater:${event}`;
      ipcRenderer.removeListener(rendererEvent, callback as any);
    },
  },
  backend: {
    status: (): Promise<{ running: boolean; port: number }> =>
      ipcRenderer.invoke("backend:status"),

    restart: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("backend:restart"),
  },
  memory: {
    stats: (): Promise<{ heapUsedMB: number; heapTotalMB: number; rssMB: number }> =>
      ipcRenderer.invoke("memory:stats"),

    cleanup: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("memory:cleanup"),
  },
  tray: {
    minimizeToTray: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("tray:minimize-to-tray"),

    restore: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("tray:restore"),
  },
  window: {
    minimize: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("window:minimize"),
    maximize: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("window:maximize"),
    close: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("window:close"),
    isMaximized: (): Promise<boolean> =>
      ipcRenderer.invoke("window:is-maximized"),
    onMaximizeChange: (callback: (maximized: boolean) => void): (() => void) => {
      const handler = (_event: Electron.IpcRendererEvent, maximized: boolean) => {
        callback(maximized);
      };
      ipcRenderer.on("window:maximize-change", handler);
      return () => {
        ipcRenderer.removeListener("window:maximize-change", handler);
      };
    },
    setMode: (mode: "full" | "floating" | "orb"): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("window:set-mode", mode),
    getMode: (): Promise<"full" | "floating" | "orb"> =>
      ipcRenderer.invoke("window:get-mode"),
  },
app: {
    quit: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("app:quit"),
    startup: {
      setSettings: (settings: { openAtLogin: boolean; startMinimized: boolean; startAsOrb: boolean }): Promise<{ ok: boolean }> =>
        ipcRenderer.invoke("startup:set-settings", settings),
      getSettings: (): Promise<{ openAtLogin: boolean; openAsHidden: boolean }> =>
        ipcRenderer.invoke("startup:get-settings"),
    },
  },
  health: {
    overview: (): Promise<{
      backend: boolean;
      backendPort: number;
      memory: { heapUsedMB: number; heapTotalMB: number; rssMB: number };
      uptime: number;
    }> => ipcRenderer.invoke("health:overview"),
    restoreAck: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("app:restore-ack"),
    onRestoreState: (callback: () => void): (() => void) => {
      const handler = () => callback();
      ipcRenderer.on("app:restore-state", handler);
      return () => {
        ipcRenderer.removeListener("app:restore-state", handler);
      };
    },
  },
  onAudioStopAll: (callback: () => void): (() => void) => {
    const handler = () => callback();
    ipcRenderer.on("audio:stop-all", handler);
    return () => {
      ipcRenderer.removeListener("audio:stop-all", handler);
    };
  },
});

// ────────────────────────────────────────────────────────────────────────────
// Legacy dash API (backward compatibility)
// ────────────────────────────────────────────────────────────────────────────
contextBridge.exposeInMainWorld("dash", {
  version: "1.0.0",
  platform: process.platform,
  updater: {
    checkForUpdates: () => ipcRenderer.invoke("updater:check"),
    startDownload: () => ipcRenderer.invoke("updater:download"),
    quitAndInstall: () => ipcRenderer.invoke("updater:install"),
    setAutoDownload: () => Promise.resolve(),
    setAutoInstallOnQuit: () => Promise.resolve(),
    on: (event: string, callback: (...args: any[]) => void): (() => void) =>
      createListener(event, callback),
    off: (event: string, callback: (...args: any[]) => void): void => {
      const rendererEvent = `updater:${event}`;
      ipcRenderer.removeListener(rendererEvent, callback as any);
    },
  },
  backend: {
    status: () => ipcRenderer.invoke("backend:status"),
    restart: () => ipcRenderer.invoke("backend:restart"),
  },
});

