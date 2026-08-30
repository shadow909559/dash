import { app, BrowserWindow, shell, ipcMain, Notification, powerMonitor } from "electron";
import { autoUpdater } from "electron-updater";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { BackendManager } from "./backend_manager";
import { SystemTray } from "./system_tray";
import { initSingleInstanceLock, setMainWindow } from "./single_instance";
import { startMemoryCleanup, stopMemoryCleanup, getMemoryStats, performCleanup } from "./memory_cleanup";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const isDev = !app.isPackaged;
let mainWindow: BrowserWindow | null = null;
let orbWindow: BrowserWindow | null = null; // Dedicated orb window
let currentWindowMode: "full" | "floating" | "orb" = "full";
const backendManager = new BackendManager();
let systemTray: SystemTray | null = null;

// ── Single Instance Lock ──────────────────────────────────────────────────

if (!initSingleInstanceLock()) {
  app.quit();
}

// ── Production-grade auto-updater for GitHub (shadow909559/dash) ──────────

autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = false;
autoUpdater.setFeedURL({
  provider: "github",
  owner: "shadow909559",
  repo: "dash",
});

// Internal state
let _updateAvailable = false;
let _updateDownloaded = false;
let _checkInProgress = false;

function sendUpdateEvent(eventName: string, data?: unknown): void {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send(`updater:${eventName}`, data);
  }
}

function showDesktopNotification(title: string, body: string): void {
  try {
    if (Notification.isSupported()) {
      new Notification({ title, body }).show();
    }
  } catch {
    // Notifications are best-effort, never crash
  }
}

// ── autoUpdater event handlers ──────────────────────────────────────────────

autoUpdater.on("checking-for-update", () => {
  _checkInProgress = true;
  sendUpdateEvent("checking");
});

autoUpdater.on("update-available", (info) => {
  _checkInProgress = false;
  _updateAvailable = true;
  sendUpdateEvent("available", {
    version: info.version,
    releaseDate: info.releaseDate,
    releaseNotes: info.releaseNotes,
  });
  showDesktopNotification("Update Available", `DASH ${info.version} is available for download.`);
});

autoUpdater.on("update-not-available", () => {
  _checkInProgress = false;
  _updateAvailable = false;
  sendUpdateEvent("notAvailable");
});

autoUpdater.on("download-progress", (progressObj) => {
  sendUpdateEvent("progress", {
    percent: progressObj.percent,
    transferred: progressObj.transferred,
    total: progressObj.total,
    bytesPerSecond: progressObj.bytesPerSecond,
    delta: progressObj.delta,
  });
});

autoUpdater.on("update-downloaded", (info) => {
  _updateDownloaded = true;
  sendUpdateEvent("downloaded", {
    version: info.version,
    releaseDate: info.releaseDate,
    releaseNotes: info.releaseNotes,
  });
  showDesktopNotification("Update Ready", "DASH update has been downloaded. Restart to install.");
});

autoUpdater.on("error", (err) => {
  _checkInProgress = false;
  const message = (err && typeof err === "object" && "message" in err)
    ? (err as Error).message
    : String(err ?? "Unknown error");

  let userMessage = message;
  if (/404|not found/i.test(message)) {
    userMessage = "No releases found for this repository.";
  } else if (/timeout|timed out|ETIMEDOUT|ECONNRESET|ENOTFOUND|EAI_AGAIN/i.test(message)) {
    userMessage = "Could not reach GitHub. Please check your internet connection and try again.";
  } else if (/unauthorized|403/i.test(message)) {
    userMessage = "Access denied. Make sure the repository is accessible.";
  } else if (/no valid/i.test(message)) {
    userMessage = "No published releases available for your platform.";
  } else if (/checksum|integrity|corrupt|signature/i.test(message)) {
    userMessage = "Download appears corrupted. Please try again.";
  }

  console.error("[autoUpdater]", message);
  sendUpdateEvent("error", userMessage);
});

// ── IPC handlers ────────────────────────────────────────────────────────────

ipcMain.handle("updater:status", () => {
  return {
    checkInProgress: _checkInProgress,
    updateAvailable: _updateAvailable,
    updateDownloaded: _updateDownloaded,
    version: app.getVersion(),
  };
});

ipcMain.handle("updater:check", async () => {
  if (_checkInProgress) return { ok: false, reason: "ALREADY_CHECKING" };
  if (isDev) {
    sendUpdateEvent("error", "Auto-updater is disabled in development mode.");
    return { ok: false, reason: "DEV_MODE" };
  }
  try {
    await autoUpdater.checkForUpdates();
    return { ok: true };
  } catch (err: unknown) {
    const message = (err && typeof err === "object" && "message" in err)
      ? (err as Error).message
      : String(err ?? "Unknown error");
    sendUpdateEvent("error", message);
    return { ok: false, reason: message };
  }
});

ipcMain.handle("updater:download", async () => {
  if (!_updateAvailable) {
    sendUpdateEvent("error", "No update available to download.");
    return { ok: false, reason: "NO_UPDATE" };
  }
  if (_updateDownloaded) {
    sendUpdateEvent("downloaded", { version: app.getVersion() });
    return { ok: false, reason: "ALREADY_DOWNLOADED" };
  }
  try {
    await autoUpdater.downloadUpdate();
    return { ok: true };
  } catch (err: unknown) {
    const message = (err && typeof err === "object" && "message" in err)
      ? (err as Error).message
      : String(err ?? "Unknown error");
    sendUpdateEvent("error", message);
    return { ok: false, reason: message };
  }
});

ipcMain.handle("updater:install", () => {
  if (!_updateDownloaded) {
    sendUpdateEvent("error", "No update has been downloaded yet.");
    return { ok: false, reason: "NOT_DOWNLOADED" };
  }
  try {
    autoUpdater.quitAndInstall();
    return { ok: true };
  } catch (err: unknown) {
    const message = (err && typeof err === "object" && "message" in err)
      ? (err as Error).message
      : String(err ?? "Unknown error");
    sendUpdateEvent("error", message);
    return { ok: false, reason: message };
  }
});

// Backend management IPC
ipcMain.handle("backend:status", () => {
  return {
    running: backendManager.isRunning(),
    port: backendManager.getPort(),
  };
});

// Device identity IPC — the renderer needs the local device token to
// authenticate with DASH Core (no login UI; Windows user is the boundary).
// The token value is NEVER logged.
let cachedDeviceToken: string | null = null;
ipcMain.handle("auth:device-token", async () => {
  try {
    if (cachedDeviceToken) return { ok: true, token: cachedDeviceToken };
    const fs = await import("node:fs");
    const path = await import("node:path");
    const { app } = await import("electron");
    const base =
      process.platform === "win32"
        ? process.env.LOCALAPPDATA || path.join(app.getPath("home"), "AppData", "Local")
        : app.getPath("home");
    const identityPath =
      process.platform === "win32"
        ? path.join(base, "DASH", "identity.json")
        : path.join(base, ".dash", "identity.json");
    const raw = fs.readFileSync(identityPath, "utf-8");
    const parsed = JSON.parse(raw) as { device_token?: string };
    if (!parsed.device_token) return { ok: false, reason: "identity file missing device_token" };
    cachedDeviceToken = parsed.device_token;
    return { ok: true, token: cachedDeviceToken };
  } catch (err) {
    console.error("[auth] failed to read DASH identity file:", (err as Error).message);
    return { ok: false, reason: "DASH identity file not readable" };
  }
});

ipcMain.handle("backend:restart", async () => {
  await backendManager.stop();
  await backendManager.start();
  return { ok: true };
});

// Memory management IPC
ipcMain.handle("memory:stats", () => {
  return getMemoryStats();
});

ipcMain.handle("memory:cleanup", () => {
  performCleanup();
  return { ok: true };
});

// System tray IPC
ipcMain.handle("tray:minimize-to-tray", () => {
  if (mainWindow) {
    mainWindow.hide();
  }
  return { ok: true };
});

ipcMain.handle("tray:restore", () => {
  if (mainWindow) {
    mainWindow.show();
    mainWindow.focus();
  }
  return { ok: true };
});

// Window control IPC
ipcMain.handle("window:minimize", () => {
  if (mainWindow) mainWindow.minimize();
  return { ok: true };
});

ipcMain.handle("window:maximize", () => {
  if (mainWindow) {
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow.maximize();
    }
  }
  return { ok: true };
});

ipcMain.handle("window:close", () => {
  if (mainWindow) mainWindow.close();
  return { ok: true };
});

ipcMain.handle("window:is-maximized", () => {
  return mainWindow?.isMaximized() ?? false;
});

// Dedicated orb window creation
function createOrbWindow(): BrowserWindow {
  const orb = new BrowserWindow({
    width: 500,
    height: 500,
    minWidth: 480,
    minHeight: 480,
    maxWidth: 560,
    maxHeight: 560,
    resizable: false,
    alwaysOnTop: true,
    frame: false,
    transparent: true,
    skipTaskbar: true,
    hasShadow: false,
    backgroundColor: "#00000000",
    webPreferences: {
      preload: isDev
        ? path.join(__dirname, "preload.js")
        : path.join(app.getAppPath(), "dist-electron", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: false,
    },
  });

  // Load the orb-specific page
  if (isDev) {
    orb.loadURL("http://localhost:5173/orb.html");
  } else {
    orb.loadFile(path.join(__dirname, "../dist/orb.html"));
  }

  // Hide main window when orb window is created
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
  }

  orb.on("closed", () => {
    orbWindow = null;
    currentWindowMode = "full";
    // Restore main window if orb is closed
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  // Handle orb window focus/blur for always-on-top behavior
  orb.on("focus", () => {
    orb.setAlwaysOnTop(true);
  });

  return orb;
}

// Close orb window and restore main window
function closeOrbWindow(): void {
  if (orbWindow && !orbWindow.isDestroyed()) {
    orbWindow.close();
    orbWindow = null;
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.setResizable(true);
    mainWindow.setMinimumSize(800, 600);
    mainWindow.setSize(1200, 800);
    mainWindow.center();
    mainWindow.setAlwaysOnTop(false);
    mainWindow.show();
  }
}

// Window mode switching
ipcMain.handle("window:set-mode", async (_, mode: "full" | "floating" | "orb") => {
  currentWindowMode = mode;

  switch (mode) {
    case "full":
      // If we're coming from orb mode, close the orb and restore main window
      if (orbWindow) {
        closeOrbWindow();
      } else if (mainWindow) {
        mainWindow.setResizable(true);
        mainWindow.setMinimumSize(800, 600);
        mainWindow.setSize(1200, 800);
        mainWindow.center();
        mainWindow.setAlwaysOnTop(false);
        mainWindow.show();
      }
      break;
    case "floating":
      // If we're coming from orb mode, close the orb first
      if (orbWindow) {
        closeOrbWindow();
      }
      if (mainWindow) {
        mainWindow.setResizable(true);
        mainWindow.setMinimumSize(400, 300);
        mainWindow.setSize(600, 400);
        mainWindow.center();
        mainWindow.setAlwaysOnTop(true);
        mainWindow.show();
      }
      break;
    case "orb":
      // Create dedicated orb window if it doesn't exist
      if (!orbWindow || orbWindow.isDestroyed()) {
        orbWindow = createOrbWindow();
      } else {
        orbWindow.show();
      }
      break;
  }
  return { ok: true };
});

ipcMain.handle("window:get-mode", () => {
  return currentWindowMode;
});

// IPC cleanup on window close
ipcMain.handle("app:quit", () => {
  app.quit();
  return { ok: true };
});

// ── Startup Settings ─────────────────────────────────────────────────────
ipcMain.handle("startup:set-settings", async (_, settings: { openAtLogin: boolean; startMinimized: boolean; startAsOrb: boolean }) => {
  app.setLoginItemSettings({
    openAtLogin: settings.openAtLogin,
    openAsHidden: settings.startMinimized,
    path: process.execPath,
  });
  return { ok: true };
});

ipcMain.handle("startup:get-settings", () => {
  const settings = app.getLoginItemSettings();
  return {
    openAtLogin: settings.openAtLogin,
    openAsHidden: settings.openAsHidden,
  };
});

// ── Health & crash recovery IPC ────────────────────────────────────────────
// Lets the renderer query current health (backend + memory) and acknowledge
// that it restored its state after a crash reload.
ipcMain.handle("health:overview", () => {
  const mem = getMemoryStats();
  return {
    backend: backendManager.isRunning(),
    backendPort: backendManager.getPort(),
    memory: mem,
    uptime: process.uptime(),
  };
});

ipcMain.handle("app:restore-ack", () => {
  // The renderer confirmed it restored its state after a crash. No-op here,
  // but reserved for future persistence hooks.
  return { ok: true };
});

// ── Window creation ─────────────────────────────────────────────────────────

function createWindow(): void {
  mainWindow = new BrowserWindow({
  width: 1200,
  height: 800,
  minWidth: 800,
  minHeight: 600,
  show: false,
  title: "DASH",

// Premium frameless DASH window with native controls
  frame: false,
  titleBarStyle: "hiddenInset",

  // Keep the glass UI visually clean — transparent + rounded for the premium orb
  transparent: true,
  backgroundColor: "#050608",
  vibrancy: "under-window",
  roundedCorners: true,

  webPreferences: {
      preload: isDev
        ? path.join(__dirname, "preload.js")
        : path.join(app.getAppPath(), "dist-electron", "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // Phase 12: Reduce memory by disabling unused features
      backgroundThrottling: true,
      spellcheck: false,
      disableDialogs: true,
      // Content Security Policy for security
      webSecurity: true,
    },
  });

  // Phase 12: Disable GPU acceleration if explicit env var is fixed
  // This saves ~200-400MB GPU memory on integrated GPUs
  if (process.env.DASH_DISABLE_GPU === "1") {
    app.disableHardwareAcceleration();
  }

// Phase 12: Memory optimization - flush unused memory when window is minimized
  mainWindow.on("hide", () => {
    performCleanup();
  });

  // ── Crash Recovery ─────────────────────────────────────────────
  // If the renderer crashes, reload it and tell the renderer to restore the orb state and conversation. This keeps DASH alive.
  let rendererCrashCount = 0;
  mainWindow.webContents.on("render-process-gone", (_event, details) => {
    console.error("[Main] Renderer process gone:", details.reason);
    showDesktopNotification("DASH", "The interface restarted to recover. Your conversation is safe.");

    if (rendererCrashCount >= 3) {
      console.error("[Main] Too many renderer crashes. Reloading fresh.");
      rendererCrashCount = 0;
      mainWindow?.webContents.reload();
      return;
    }

    rendererCrashCount++;
    // Reload after a brief delay to let the process settle.
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.reload();
        // Tell the renderer to restore state after reload.
        mainWindow.webContents.once("did-finish-load", () => {
          mainWindow?.webContents.send("app:restore-state");
        });
      }
    }, 800);
  });

  // Reset crash count on a successful load.
  mainWindow.webContents.on("did-finish-load", () => {
    rendererCrashCount = 0;
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow?.show();
  });

  // Tell renderer of window state changes
  mainWindow.on("maximize", () => {
    mainWindow?.webContents.send("window:maximize-change", true);
  });

  mainWindow.on("unmaximize", () => {
    mainWindow?.webContents.send("window:maximize-change", false);
  });

  // Minimized to tray instead of closing
  mainWindow.on("close", (event) => {
    if (!(app as any).isQuitting) {
      event.preventDefault();
      // Stop all audio before hiding
      mainWindow?.webContents.send("audio:stop-all");
      mainWindow?.hide();
      showDesktopNotification("DASH", "DASH is still running in the system tray.");
    }
  });

  // Lock screen detection - Windows session lock/unlock
  // DASH respects Windows security boundaries and does not bypass authentication
  // When locked, DASH continues running in background but UI is minimized
  // When unlocked, DASH can restore its earlier state
  // Using powerMonitor suspend/resume as approximation for lock screen behavior
  let wasVisibleBeforeLock = false;

  powerMonitor.on("suspend", () => {
    console.log("[Main] System suspending - DASH will continue in background");
    if (mainWindow && !mainWindow.isDestroyed()) {
      wasVisibleBeforeLock = mainWindow.isVisible();
      mainWindow.hide();
    }
  });

  powerMonitor.on("resume", () => {
    console.log("[Main] System resuming - restoring DASH if it was visible");
    if (mainWindow && !mainWindow.isDestroyed() && wasVisibleBeforeLock) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  if (isDev && process.env.VITE_DEV_SERVER_URL) {
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
    mainWindow.webContents.openDevTools({ mode: "detach" });
  } else {
    mainWindow.loadFile(path.join(app.getAppPath(), "dist", "index.html"));
  }

  setMainWindow(mainWindow);

  // Emit maximize state changes to renderer
  mainWindow.on("maximize", () => {
    mainWindow?.webContents.send("window:maximize-change", true);
  });
  mainWindow.on("unmaximize", () => {
    mainWindow?.webContents.send("window:maximize-change", false);
  });

  // Create system tray
  systemTray = new SystemTray(mainWindow);
}

// ── App lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  // Fix cache access denied errors by setting proper cache directory
  app.setPath('cache', path.join(app.getPath('userData'), 'Cache'));
  // Disable GPU disk cache to prevent creation errors
  app.commandLine.appendSwitch('disable-gpu-disk-cache');
  app.commandLine.appendSwitch('disable-software-rasterizer');
  
  // Start the Python backend
  try {
    await backendManager.start();
    // Wait for backend to become healthy before reporting success
    const maxWaitTime = 30000; // 30 seconds max wait
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitTime) {
      if (backendManager.isRunning()) {
        console.log("[Main] Backend started successfully and verified healthy");
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    
    if (!backendManager.isRunning()) {
      console.error("[Main] Backend startup timed out - not healthy after 30 seconds");
      showDesktopNotification("DASH Backend Warning", "Backend started but not responding to health checks. Some features may not work.");
    }
  } catch (err) {
    console.error("[Main] Failed to start backend:", err);
    // Show error to user via notification
    showDesktopNotification("DASH Backend Error", `Failed to start the backend: ${err instanceof Error ? err.message : String(err)}`);
  }

  createWindow();

  // Start periodic memory cleanup
  startMemoryCleanup();
  console.log("[Main] Memory cleanup scheduler started");

  // Wait 5 seconds after startup, then check for updates (production only)
  if (!isDev) {
    setTimeout(() => {
      autoUpdater.checkForUpdates().catch((err: Error) => {
        console.log("[autoUpdater] Initial check failed (will retry later):", err.message);
      });
    }, 5000);
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    // Don't quit - minimized to tray instead
  }
});

app.on("before-quit", async () => {
  (app as any).isQuitting = true;
  stopMemoryCleanup();
  if (systemTray) {
    systemTray.destroy();
  }
  // Gracefully stop the backend
  await backendManager.stop();
});