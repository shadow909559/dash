import { app, BrowserWindow, shell, ipcMain, nativeTheme, Tray, Menu, Notification, dialog, clipboard, nativeImage } from "electron";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = !app.isPackaged;

let mainWindow: BrowserWindow | null = null;
let tray: Tray | null = null;

// Window state persistence
const STATE_PATH = path.join(app.getPath("userData"), "window-state.json");

interface WindowState {
  x?: number;
  y?: number;
  width: number;
  height: number;
  isMaximized: boolean;
  isFullscreen: boolean;
}

function loadWindowState(): WindowState {
  try {
    if (fs.existsSync(STATE_PATH)) {
      return JSON.parse(fs.readFileSync(STATE_PATH, "utf-8"));
    }
  } catch { /* ignore */ }
  return { width: 1200, height: 800, isMaximized: false, isFullscreen: false };
}

function saveWindowState(state: WindowState) {
  try {
    const dir = path.dirname(STATE_PATH);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2));
  } catch { /* ignore */ }
}

function createWindow() {
  const savedState = loadWindowState();

  mainWindow = new BrowserWindow({
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
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
    },
  });

  if (savedState.isMaximized) mainWindow.maximize();
  if (savedState.isFullscreen) mainWindow.setFullScreen(true);

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
    if (process.platform === "win32") {
      try { mainWindow?.setBackgroundMaterial("mica"); } catch { /* fallback */ }
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
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.on("close", (e) => {
    if (shouldMinimizeToTray && !isQuitting) {
      e.preventDefault();
      mainWindow?.hide();
      if (tray) {
        tray.displayBalloon({
          title: "DASH",
          content: "DASH is running in the system tray"
        });
      }
    }
  });

  mainWindow.on("closed", () => { mainWindow = null; });

  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

function createTray() {
  const iconPath = path.join(__dirname, "../public/icon.png");
  let trayIcon: Electron.NativeImage;
  try {
    trayIcon = nativeImage.createFromPath(iconPath);
  } catch {
    trayIcon = nativeImage.createEmpty();
  }

  tray = new Tray(trayIcon);
  tray.setToolTip("DASH");

  const contextMenu = Menu.buildFromTemplate([
    { label: "Show DASH", click: () => { mainWindow?.show(); mainWindow?.focus(); } },
    { type: "separator" },
    { label: "Quit", click: () => { app.quit(); } },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on("double-click", () => { mainWindow?.show(); mainWindow?.focus(); });
}

// Track if we should minimize to tray instead of closing
let shouldMinimizeToTray = false;
let isQuitting = false;

function setupIpc() {
  // Window controls
  ipcMain.on("window:minimize", () => mainWindow?.minimize());
  ipcMain.on("window:maximize", () => {
    mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize();
  });
  ipcMain.on("window:close", () => mainWindow?.close());
  ipcMain.handle("window:isMaximized", () => mainWindow?.isMaximized() ?? false);

  // File dialogs
  ipcMain.handle("dialog:openFile", async (_event, options) => {
    return await dialog.showOpenDialog(mainWindow!, { properties: ["openFile"], ...options });
  });
  ipcMain.handle("dialog:saveFile", async (_event, options) => {
    return await dialog.showSaveDialog(mainWindow!, { ...options });
  });

  // Clipboard
  ipcMain.handle("clipboard:readText", () => clipboard.readText());
  ipcMain.handle("clipboard:writeText", (_event, text: string) => { clipboard.writeText(text); });

  // Notifications
  ipcMain.handle("notification:show", (_event, { title, body }: { title: string; body: string }) => {
    new Notification({ title, body }).show();
  });

  // App info
  ipcMain.handle("app:getPath", (_event, name: string) => app.getPath(name as any));
  ipcMain.handle("app:getVersion", () => app.getVersion());

  // System tray
  ipcMain.on("tray:minimizeToTray", () => { mainWindow?.hide(); });
  
  ipcMain.on("tray:enableMinToTray", () => { 
    shouldMinimizeToTray = true;
  });
  ipcMain.on("tray:disableMinToTray", () => { 
    shouldMinimizeToTray = false;
  });

  // Auto-launch
  ipcMain.handle("settings:getAutoLaunch", () => app.getLoginItemSettings().openAtLogin);
  ipcMain.handle("settings:setAutoLaunch", (_event, enabled: boolean) => {
    app.setLoginItemSettings({ openAtLogin: enabled });
  });
  
  // Window start minimized
  ipcMain.on("window:setStartMinimized", () => {
    // This setting will be persisted by the settings store
    // If true, we'll start minimized to tray next time the app launches
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

  // Theme
  ipcMain.handle("theme:getNative", () => nativeTheme.shouldUseDarkColors ? "dark" : "light");
  nativeTheme.on("updated", () => {
    mainWindow?.webContents.send("theme:changed", nativeTheme.shouldUseDarkColors ? "dark" : "light");
  });
}

// Read persisted settings from zustand storage
function loadPersistedSettings() {
  try {
    const settingsPath = path.join(app.getPath("userData"), "settings-storage.json");
    if (fs.existsSync(settingsPath)) {
      const data = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
      return data.state || {};
    }
  } catch { /* ignore */ }
  return {};
}

app.whenReady().then(() => {
  setupIpc();
  createWindow();
  createTray();

  // Check if we should start minimized
  const settings = loadPersistedSettings();
  if (settings.startMinimized) {
    mainWindow?.hide();
    if (tray) {
      tray.displayBalloon({
        title: "DASH",
        content: "DASH is running in the system tray"
      });
    }
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else mainWindow?.show();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
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