import { app, BrowserWindow, shell, ipcMain, Notification } from "electron";
import { autoUpdater } from "electron-updater";
import path from "node:path";
import { fileURLToPath } from "node:url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const isDev = !app.isPackaged;
let mainWindow = null;
// Auto-updater configuration
autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = false;
function sendUpdateEvent(eventName, data) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(`updater:${eventName}`, data);
    }
}
function showDesktopNotification(title, body) {
    if (Notification.isSupported()) {
        new Notification({ title, body }).show();
    }
}
// Auto-updater event handlers
autoUpdater.on("checking-for-update", () => {
    sendUpdateEvent("checking");
});
autoUpdater.on("update-available", (info) => {
    sendUpdateEvent("available", info);
    showDesktopNotification("Update Available", "A new version of DASH is available for download.");
});
autoUpdater.on("update-not-available", (info) => {
    sendUpdateEvent("not-available", info);
});
autoUpdater.on("download-progress", (progressObj) => {
    sendUpdateEvent("progress", {
        percent: progressObj.percent,
        transferred: progressObj.transferred,
        total: progressObj.total,
        bytesPerSecond: progressObj.bytesPerSecond
    });
});
autoUpdater.on("update-downloaded", (info) => {
    sendUpdateEvent("downloaded", info);
    showDesktopNotification("Update Ready", "DASH update has been downloaded. Restart to install.");
});
autoUpdater.on("error", (err) => {
    console.error("Auto-updater error:", err);
    sendUpdateEvent("error", err.message);
});
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
        },
    });
    mainWindow.once("ready-to-show", () => {
        mainWindow?.show();
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
        // In production, the dist folder is in the same directory as dist-electron
        mainWindow.loadFile(path.join(app.getAppPath(), "dist", "index.html"));
    }
}
// IPC handlers for updater control
ipcMain.handle("updater:check-for-updates", () => {
    if (!isDev) {
        autoUpdater.checkForUpdates().catch(err => {
            console.error("Failed to check for updates:", err);
        });
    }
});
ipcMain.handle("updater:start-download", () => {
    autoUpdater.downloadUpdate().catch(err => {
        console.error("Failed to download update:", err);
    });
});
ipcMain.handle("updater:quit-and-install", () => {
    autoUpdater.quitAndInstall();
});
ipcMain.handle("updater:set-auto-download", (_, value) => {
    autoUpdater.autoDownload = value;
});
ipcMain.handle("updater:set-auto-install-on-quit", (_, value) => {
    autoUpdater.autoInstallOnAppQuit = value;
});
app.whenReady().then(() => {
    createWindow();
    // Wait 5 seconds before checking for updates on startup
    if (!isDev) {
        setTimeout(() => {
            autoUpdater.checkForUpdates().catch(err => {
                console.log("GitHub unavailable, will retry later:", err.message);
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
        app.quit();
    }
});
