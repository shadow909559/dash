"use strict";
const electron = require("electron");
electron.contextBridge.exposeInMainWorld("dash", {
  version: "0.1.0",
  platform: process.platform,
  // Window controls
  window: {
    minimize: () => electron.ipcRenderer.send("window:minimize"),
    maximize: () => electron.ipcRenderer.send("window:maximize"),
    close: () => electron.ipcRenderer.send("window:close"),
    isMaximized: () => electron.ipcRenderer.invoke("window:isMaximized")
  },
  // File dialogs
  dialog: {
    openFile: (options) => electron.ipcRenderer.invoke("dialog:openFile", options),
    saveFile: (options) => electron.ipcRenderer.invoke("dialog:saveFile", options)
  },
  // Clipboard
  clipboard: {
    readText: () => electron.ipcRenderer.invoke("clipboard:readText"),
    writeText: (text) => electron.ipcRenderer.invoke("clipboard:writeText", text)
  },
  // Notifications
  notification: {
    show: (title, body) => electron.ipcRenderer.invoke("notification:show", { title, body })
  },
  // System tray
  tray: {
    minimizeToTray: () => electron.ipcRenderer.send("tray:minimizeToTray")
  },
  // App info
  app: {
    getPath: (name) => electron.ipcRenderer.invoke("app:getPath", name),
    getVersion: () => electron.ipcRenderer.invoke("app:getVersion")
  },
  // Settings
  settings: {
    getAutoLaunch: () => electron.ipcRenderer.invoke("settings:getAutoLaunch"),
    setAutoLaunch: (enabled) => electron.ipcRenderer.invoke("settings:setAutoLaunch", enabled)
  },
  // Theme
  theme: {
    getNative: () => electron.ipcRenderer.invoke("theme:getNative"),
    onChange: (callback) => {
      electron.ipcRenderer.on("theme:changed", (_event, theme) => callback(theme));
    }
  }
});
