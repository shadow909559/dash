import { contextBridge, ipcRenderer } from "electron";
contextBridge.exposeInMainWorld("dash", {
    version: "0.1.0",
    platform: process.platform,
    // Window controls
    window: {
        minimize: () => ipcRenderer.send("window:minimize"),
        maximize: () => ipcRenderer.send("window:maximize"),
        close: () => ipcRenderer.send("window:close"),
        isMaximized: () => ipcRenderer.invoke("window:isMaximized"),
    },
    // File dialogs
    dialog: {
        openFile: (options) => ipcRenderer.invoke("dialog:openFile", options),
        saveFile: (options) => ipcRenderer.invoke("dialog:saveFile", options),
    },
    // Clipboard
    clipboard: {
        readText: () => ipcRenderer.invoke("clipboard:readText"),
        writeText: (text) => ipcRenderer.invoke("clipboard:writeText", text),
    },
    // Notifications
    notification: {
        show: (title, body) => ipcRenderer.invoke("notification:show", { title, body }),
    },
    // System tray
    tray: {
        minimizeToTray: () => ipcRenderer.send("tray:minimizeToTray"),
    },
    // App info
    app: {
        getPath: (name) => ipcRenderer.invoke("app:getPath", name),
        getVersion: () => ipcRenderer.invoke("app:getVersion"),
    },
    // Settings
    settings: {
        getAutoLaunch: () => ipcRenderer.invoke("settings:getAutoLaunch"),
        setAutoLaunch: (enabled) => ipcRenderer.invoke("settings:setAutoLaunch", enabled),
    },
    // Theme
    theme: {
        getNative: () => ipcRenderer.invoke("theme:getNative"),
        onChange: (callback) => {
            ipcRenderer.on("theme:changed", (_event, theme) => callback(theme));
        },
    },
});
