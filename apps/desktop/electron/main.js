import { app, BrowserWindow, shell, ipcMain, Notification } from "electron";
import { autoUpdater } from "electron-updater";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { BackendManager } from "./backend_manager";
import { SystemTray } from "./system_tray";
import { initSingleInstanceLock, setMainWindow } from "./single_instance";
import { startMemoryCleanup, stopMemoryCleanup, getMemoryStats, performCleanup } from "./memory_cleanup";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = !app.isPackaged;
let mainWindow = null;
const backendManager = new BackendManager();
let systemTray = null;
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
function sendUpdateEvent(eventName, data) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(`updater:${eventName}`, data);
    }
}
function showDesktopNotification(title, body) {
    try {
        if (Notification.isSupported()) {
            new Notification({ title, body }).show();
        }
    }
    catch {
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
        ? err.message
        : String(err ?? "Unknown error");
    let userMessage = message;
    if (/404|not found/i.test(message)) {
        userMessage = "No releases found for this repository.";
    }
    else if (/timeout|timed out|ETIMEDOUT|ECONNRESET|ENOTFOUND|EAI_AGAIN/i.test(message)) {
        userMessage = "Could not reach GitHub. Please check your internet connection and try again.";
    }
    else if (/unauthorized|403/i.test(message)) {
        userMessage = "Access denied. Make sure the repository is accessible.";
    }
    else if (/no valid/i.test(message)) {
        userMessage = "No published releases available for your platform.";
    }
    else if (/checksum|integrity|corrupt|signature/i.test(message)) {
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
    if (_checkInProgress)
        return { ok: false, reason: "ALREADY_CHECKING" };
    if (isDev) {
        sendUpdateEvent("error", "Auto-updater is disabled in development mode.");
        return { ok: false, reason: "DEV_MODE" };
    }
    try {
        await autoUpdater.checkForUpdates();
        return { ok: true };
    }
    catch (err) {
        const message = (err && typeof err === "object" && "message" in err)
            ? err.message
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
    }
    catch (err) {
        const message = (err && typeof err === "object" && "message" in err)
            ? err.message
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
    }
    catch (err) {
        const message = (err && typeof err === "object" && "message" in err)
            ? err.message
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
// IPC cleanup on window close
ipcMain.handle("app:quit", () => {
    app.quit();
    return { ok: true };
});
// ── Window creation ─────────────────────────────────────────────────────────
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        show: false,
        title: "DASH",
        backgroundColor: "#0a0a0f",
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
        },
    });
    // Phase 12: Disable GPU acceleration if explicit env var is set
    // This saves ~200-400MB GPU memory on integrated GPUs
    if (process.env.DASH_DISABLE_GPU === "1") {
        app.disableHardwareAcceleration();
    }
    // Phase 12: Memory optimization - flush unused memory when window is hidden
    mainWindow.on("hide", () => {
        performCleanup();
    });
    mainWindow.once("ready-to-show", () => {
        mainWindow?.show();
    });
    // Minimize to tray instead of closing
    mainWindow.on("close", (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow?.hide();
            showDesktopNotification("DASH", "DASH is still running in the system tray.");
        }
    });
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: "deny" };
    });
    if (isDev && process.env.VITE_DEV_SERVER_URL) {
        mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL);
        mainWindow.webContents.openDevTools({ mode: "detach" });
    }
    else {
        mainWindow.loadFile(path.join(app.getAppPath(), "dist", "index.html"));
    }
    setMainWindow(mainWindow);
    // Create system tray
    systemTray = new SystemTray(mainWindow);
}
// ── App lifecycle ───────────────────────────────────────────────────────────
app.whenReady().then(async () => {
    // Start the Python backend
    try {
        await backendManager.start();
        console.log("[Main] Backend started successfully");
    }
    catch (err) {
        console.error("[Main] Failed to start backend:", err);
    }
    createWindow();
    // Start periodic memory cleanup
    startMemoryCleanup();
    console.log("[Main] Memory cleanup scheduler started");
    // Wait 5 seconds after startup, then check for updates (production only)
    if (!isDev) {
        setTimeout(() => {
            autoUpdater.checkForUpdates().catch((err) => {
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
        // Don't quit - minimize to tray instead
    }
});
app.on("before-quit", async () => {
    app.isQuitting = true;
    stopMemoryCleanup();
    if (systemTray) {
        systemTray.destroy();
    }
    // Gracefully stop the backend
    await backendManager.stop();
});
