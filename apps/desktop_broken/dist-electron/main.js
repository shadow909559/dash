"use strict";
const electron = require("electron");
const path = require("node:path");
const fs = require("node:fs");
const node_url = require("node:url");
var _documentCurrentScript = typeof document !== "undefined" ? document.currentScript : null;
const __dirname$1 = path.dirname(node_url.fileURLToPath(typeof document === "undefined" ? require("url").pathToFileURL(__filename).href : _documentCurrentScript && _documentCurrentScript.tagName.toUpperCase() === "SCRIPT" && _documentCurrentScript.src || new URL("main.js", document.baseURI).href));
const isDev = !electron.app.isPackaged;
let mainWindow = null;
let tray = null;
const STATE_PATH = path.join(electron.app.getPath("userData"), "window-state.json");
function loadWindowState() {
  try {
    if (fs.existsSync(STATE_PATH)) {
      return JSON.parse(fs.readFileSync(STATE_PATH, "utf-8"));
    }
  } catch {
  }
  return { width: 1200, height: 800, isMaximized: false, isFullscreen: false };
}
function saveWindowState(state) {
  try {
    const dir = path.dirname(STATE_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  } catch {
  }
}
function createWindow() {
  const savedState = loadWindowState();
  mainWindow = new electron.BrowserWindow({
    width: savedState.width,
    height: savedState.height,
    x: savedState.x,
    y: savedState.y,
    minWidth: 800,
    minHeight: 600,
    show: false,
    title: "DASH",
    backgroundColor: "#0a0a0f",
    frame: false,
    titleBarStyle: "hidden",
    roundedCorners: true,
    transparent: false,
    hasShadow: true,
    webPreferences: {
      preload: path.join(__dirname$1, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true
    }
  });
  if (savedState.isMaximized) mainWindow.maximize();
  if (savedState.isFullscreen) mainWindow.setFullScreen(true);
  mainWindow.once("ready-to-show", () => {
    mainWindow == null ? void 0 : mainWindow.show();
    if (process.platform === "win32") {
      try {
        mainWindow == null ? void 0 : mainWindow.setBackgroundMaterial("mica");
      } catch {
      }
    }
  });
  const updateState = () => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    const isMax = mainWindow.isMaximized();
    const isFull = mainWindow.isFullScreen();
    if (!isMax && !isFull) {
      const bounds = mainWindow.getBounds();
      saveWindowState({ ...bounds, isMaximized: false, isFullscreen: false });
    } else {
      saveWindowState({ width: 1200, height: 800, isMaximized: isMax, isFullscreen: isFull });
    }
  };
  mainWindow.on("resize", updateState);
  mainWindow.on("move", updateState);
  mainWindow.on("maximize", updateState);
  mainWindow.on("unmaximize", updateState);
  mainWindow.on("enter-full-screen", updateState);
  mainWindow.on("leave-full-screen", updateState);
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    electron.shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.on("close", (e) => {
    if (shouldMinimizeToTray && !isQuitting) {
      e.preventDefault();
      mainWindow == null ? void 0 : mainWindow.hide();
      if (tray) {
        tray.displayBalloon({
          title: "DASH",
          content: "DASH is running in the system tray"
        });
      }
    }
  });
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname$1, "../dist/index.html"));
  }
}
function createTray() {
  const iconPath = path.join(__dirname$1, "../public/icon.png");
  let trayIcon;
  try {
    trayIcon = electron.nativeImage.createFromPath(iconPath);
  } catch {
    trayIcon = electron.nativeImage.createEmpty();
  }
  tray = new electron.Tray(trayIcon);
  tray.setToolTip("DASH");
  const contextMenu = electron.Menu.buildFromTemplate([
    { label: "Show DASH", click: () => {
      mainWindow == null ? void 0 : mainWindow.show();
      mainWindow == null ? void 0 : mainWindow.focus();
    } },
    { type: "separator" },
    { label: "Quit", click: () => {
      electron.app.quit();
    } }
  ]);
  tray.setContextMenu(contextMenu);
  tray.on("double-click", () => {
    mainWindow == null ? void 0 : mainWindow.show();
    mainWindow == null ? void 0 : mainWindow.focus();
  });
}
let shouldMinimizeToTray = false;
let isQuitting = false;
function setupIpc() {
  electron.ipcMain.on("window:minimize", () => mainWindow == null ? void 0 : mainWindow.minimize());
  electron.ipcMain.on("window:maximize", () => {
    (mainWindow == null ? void 0 : mainWindow.isMaximized()) ? mainWindow.unmaximize() : mainWindow == null ? void 0 : mainWindow.maximize();
  });
  electron.ipcMain.on("window:close", () => mainWindow == null ? void 0 : mainWindow.close());
  electron.ipcMain.handle("window:isMaximized", () => (mainWindow == null ? void 0 : mainWindow.isMaximized()) ?? false);
  electron.ipcMain.handle("dialog:openFile", async (_event, options) => {
    return await electron.dialog.showOpenDialog(mainWindow, { properties: ["openFile"], ...options });
  });
  electron.ipcMain.handle("dialog:saveFile", async (_event, options) => {
    return await electron.dialog.showSaveDialog(mainWindow, { ...options });
  });
  electron.ipcMain.handle("clipboard:readText", () => electron.clipboard.readText());
  electron.ipcMain.handle("clipboard:writeText", (_event, text) => {
    electron.clipboard.writeText(text);
  });
  electron.ipcMain.handle("notification:show", (_event, { title, body }) => {
    new electron.Notification({ title, body }).show();
  });
  electron.ipcMain.handle("app:getPath", (_event, name) => electron.app.getPath(name));
  electron.ipcMain.handle("app:getVersion", () => electron.app.getVersion());
  electron.ipcMain.on("tray:minimizeToTray", () => {
    mainWindow == null ? void 0 : mainWindow.hide();
  });
  electron.ipcMain.on("tray:enableMinToTray", () => {
    shouldMinimizeToTray = true;
  });
  electron.ipcMain.on("tray:disableMinToTray", () => {
    shouldMinimizeToTray = false;
  });
  electron.ipcMain.handle("settings:getAutoLaunch", () => electron.app.getLoginItemSettings().openAtLogin);
  electron.ipcMain.handle("settings:setAutoLaunch", (_event, enabled) => {
    electron.app.setLoginItemSettings({ openAtLogin: enabled });
  });
  electron.ipcMain.on("window:setStartMinimized", () => {
    if (mainWindow) {
      mainWindow.hide();
      if (tray) {
        tray.displayBalloon({
          title: "DASH",
          content: "DASH is running in the system tray"
        });
      }
    }
  });
  electron.ipcMain.handle("theme:getNative", () => electron.nativeTheme.shouldUseDarkColors ? "dark" : "light");
  electron.nativeTheme.on("updated", () => {
    mainWindow == null ? void 0 : mainWindow.webContents.send("theme:changed", electron.nativeTheme.shouldUseDarkColors ? "dark" : "light");
  });
}
function loadPersistedSettings() {
  try {
    const settingsPath = path.join(electron.app.getPath("userData"), "settings-storage.json");
    if (fs.existsSync(settingsPath)) {
      const data = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
      return data.state || {};
    }
  } catch {
  }
  return {};
}
electron.app.whenReady().then(() => {
  setupIpc();
  createWindow();
  createTray();
  const settings = loadPersistedSettings();
  if (settings.startMinimized) {
    mainWindow == null ? void 0 : mainWindow.hide();
    if (tray) {
      tray.displayBalloon({
        title: "DASH",
        content: "DASH is running in the system tray"
      });
    }
  }
  electron.app.on("activate", () => {
    if (electron.BrowserWindow.getAllWindows().length === 0) createWindow();
    else mainWindow == null ? void 0 : mainWindow.show();
  });
});
electron.app.on("window-all-closed", () => {
  if (process.platform !== "darwin") electron.app.quit();
});
electron.app.on("before-quit", () => {
  isQuitting = true;
  if (mainWindow && !mainWindow.isDestroyed()) {
    const isMax = mainWindow.isMaximized();
    const isFull = mainWindow.isFullScreen();
    if (!isMax && !isFull) {
      const bounds = mainWindow.getBounds();
      saveWindowState({ ...bounds, isMaximized: false, isFullscreen: false });
    } else {
      saveWindowState({ width: 1200, height: 800, isMaximized: isMax, isFullscreen: isFull });
    }
  }
});
