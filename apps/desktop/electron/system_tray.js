/**
 * SystemTray - Manages the Electron system tray icon and menu.
 *
 * Features:
 *   - System tray icon with context menu
 *   - Minimize to tray on close
 *   - Restore from tray
 *   - Quick actions (open, quit)
 *   - Background mode indicator
 */
import { app, Menu, Tray, nativeImage } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
export class SystemTray {
    constructor(mainWindow) {
        this.tray = null;
        this.mainWindow = null;
        this.mainWindow = mainWindow;
        // Create a simple 16x16 icon (fallback - in production use actual icon file)
        this.iconPath = path.join(__dirname, "..", "public", "icon.png");
        this.createTray();
    }
    createTray() {
        let icon;
        try {
            icon = nativeImage.createFromPath(this.iconPath);
            if (icon.isEmpty()) {
                icon = this.createFallbackIcon();
            }
        }
        catch {
            icon = this.createFallbackIcon();
        }
        this.tray = new Tray(icon);
        this.tray.setToolTip("DASH - AI Operating System");
        const contextMenu = Menu.buildFromTemplate([
            {
                label: "Open DASH",
                click: () => this.restore(),
            },
            { type: "separator" },
            {
                label: "Toggle Background Mode",
                type: "checkbox",
                checked: false,
                click: (menuItem) => {
                    if (menuItem.checked) {
                        this.enableBackgroundMode();
                    }
                    else {
                        this.disableBackgroundMode();
                    }
                },
            },
            { type: "separator" },
            {
                label: "Quit",
                click: () => {
                    app.isQuitting = true; // custom flag
                    app.quit();
                },
            },
        ]);
        this.tray.setContextMenu(contextMenu);
        // Double-click to restore
        this.tray.on("double-click", () => {
            this.restore();
        });
    }
    createFallbackIcon() {
        // Create a simple 16x16 colored icon using raw RGBA data
        const size = 16;
        const buffer = Buffer.alloc(size * size * 4);
        for (let y = 0; y < size; y++) {
            for (let x = 0; x < size; x++) {
                const offset = (y * size + x) * 4;
                // Purple/blue gradient
                buffer[offset] = 100 + Math.floor((x / size) * 50); // R
                buffer[offset + 1] = 50 + Math.floor((y / size) * 50); // G
                buffer[offset + 2] = 200; // B
                buffer[offset + 3] = 255; // A
            }
        }
        return nativeImage.createFromBuffer(buffer, { width: size, height: size });
    }
    restore() {
        if (this.mainWindow) {
            if (this.mainWindow.isMinimized()) {
                this.mainWindow.restore();
            }
            this.mainWindow.show();
            this.mainWindow.focus();
        }
    }
    enableBackgroundMode() {
        if (this.mainWindow) {
            this.mainWindow.setSkipTaskbar(true);
            this.mainWindow.hide();
        }
    }
    disableBackgroundMode() {
        if (this.mainWindow) {
            this.mainWindow.setSkipTaskbar(false);
            this.mainWindow.show();
        }
    }
    setWindow(mainWindow) {
        this.mainWindow = mainWindow;
    }
    destroy() {
        if (this.tray) {
            this.tray.destroy();
            this.tray = null;
        }
    }
}
