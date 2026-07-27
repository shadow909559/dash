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
  app: {
    quit: (): Promise<{ ok: boolean }> =>
      ipcRenderer.invoke("app:quit"),
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

