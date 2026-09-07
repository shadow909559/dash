/**
 * SingleInstanceLock - Ensures only one instance of DASH runs at a time.
 *
 * Uses Electron's app.requestSingleInstanceLock() to detect duplicate
 * instances and focus the existing window.
 */
import { BrowserWindow } from "electron";
/**
 * Initialize the single instance lock.
 * Call this in app.whenReady() before creating any windows.
 *
 * Returns true if this is the primary instance (should continue),
 * false if a duplicate instance was detected (should quit).
 */
export declare function initSingleInstanceLock(): boolean;
/**
 * Set the main window reference for focus-on-second-instance.
 */
export declare function setMainWindow(window: BrowserWindow): void;
