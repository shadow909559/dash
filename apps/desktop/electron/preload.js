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
    auth: {
        deviceToken: () => ipcRenderer.invoke("auth:device-token"),
    },
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
    window: {
        minimize: () => ipcRenderer.invoke("window:minimize"),
        maximize: () => ipcRenderer.invoke("window:maximize"),
        close: () => ipcRenderer.invoke("window:close"),
        isMaximized: () => ipcRenderer.invoke("window:is-maximized"),
        onMaximizeChange: (callback) => {
            const handler = (_event, maximized) => {
                callback(maximized);
            };
            ipcRenderer.on("window:maximize-change", handler);
            return () => {
                ipcRenderer.removeListener("window:maximize-change", handler);
            };
        },
        setMode: (mode) => ipcRenderer.invoke("window:set-mode", mode),
        getMode: () => ipcRenderer.invoke("window:get-mode"),
    },
    app: {
        quit: () => ipcRenderer.invoke("app:quit"),
        startup: {
            setSettings: (settings) => ipcRenderer.invoke("startup:set-settings", settings),
            getSettings: () => ipcRenderer.invoke("startup:get-settings"),
        },
    },
    health: {
        overview: () => ipcRenderer.invoke("health:overview"),
        restoreAck: () => ipcRenderer.invoke("app:restore-ack"),
        onRestoreState: (callback) => {
            const handler = () => callback();
            ipcRenderer.on("app:restore-state", handler);
            return () => {
                ipcRenderer.removeListener("app:restore-state", handler);
            };
        },
    },
    onAudioStopAll: (callback) => {
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
