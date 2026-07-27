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
import { BrowserWindow } from "electron";
export declare class SystemTray {
    private tray;
    private mainWindow;
    private readonly iconPath;
    constructor(mainWindow: BrowserWindow);
    private createTray;
    private createFallbackIcon;
    private restore;
    private enableBackgroundMode;
    private disableBackgroundMode;
    setWindow(mainWindow: BrowserWindow): void;
    destroy(): void;
}
