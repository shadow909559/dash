import { contextBridge, ipcRenderer } from "electron";
contextBridge.exposeInMainWorld("dash", {
    version: "0.1.1",
    platform: process.platform,
    // Updater IPC methods
    updater: {
        checkForUpdates: () => ipcRenderer.invoke("updater:check-for-updates"),
        startDownload: () => ipcRenderer.invoke("updater:start-download"),
        quitAndInstall: () => ipcRenderer.invoke("updater:quit-and-install"),
        setAutoDownload: (value) => ipcRenderer.invoke("updater:set-auto-download", value),
        setAutoInstallOnQuit: (value) => ipcRenderer.invoke("updater:set-auto-install-on-quit", value),
        on: (event, callback) => {
            const rendererEvent = `updater:${event}`;
            ipcRenderer.on(rendererEvent, (_, data) => callback(data));
            return () => ipcRenderer.removeListener(rendererEvent, callback);
        },
        off: (event, callback) => {
            const rendererEvent = `updater:${event}`;
            ipcRenderer.removeListener(rendererEvent, callback);
        }
    }
});
