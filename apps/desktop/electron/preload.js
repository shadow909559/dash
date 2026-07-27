import { contextBridge, ipcRenderer } from "electron";
/** Shared listener handler factory to ensure consistent cleanup */
function createListener(event, callback) {
    const rendererEvent = `updater:${event}`;
    const handler = (_event, data) => {
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
        status: () => ipcRenderer.invoke("updater:status"),
        check: () => ipcRenderer.invoke("updater:check"),
        download: () => ipcRenderer.invoke("updater:download"),
        install: () => ipcRenderer.invoke("updater:install"),
        on: (event, callback) => createListener(event, callback),
        off: (event, callback) => {
            const rendererEvent = `updater:${event}`;
            ipcRenderer.removeListener(rendererEvent, callback);
        },
    },
    backend: {
        status: () => ipcRenderer.invoke("backend:status"),
        restart: () => ipcRenderer.invoke("backend:restart"),
    },
    memory: {
        stats: () => ipcRenderer.invoke("memory:stats"),
        cleanup: () => ipcRenderer.invoke("memory:cleanup"),
    },
    tray: {
        minimizeToTray: () => ipcRenderer.invoke("tray:minimize-to-tray"),
        restore: () => ipcRenderer.invoke("tray:restore"),
    },
    app: {
        quit: () => ipcRenderer.invoke("app:quit"),
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
        on: (event, callback) => createListener(event, callback),
        off: (event, callback) => {
            const rendererEvent = `updater:${event}`;
            ipcRenderer.removeListener(rendererEvent, callback);
        },
    },
    backend: {
        status: () => ipcRenderer.invoke("backend:status"),
        restart: () => ipcRenderer.invoke("backend:restart"),
    },
});
