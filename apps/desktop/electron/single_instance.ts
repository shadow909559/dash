/**
 * SingleInstanceLock - Ensures only one instance of DASH runs at a time.
 *
 * Uses Electron's app.requestSingleInstanceLock() to detect duplicate
 * instances and focus the existing window.
 */

import { app, BrowserWindow } from "electron";

let mainWindow: BrowserWindow | null = null;

/**
 * Initialize the single instance lock.
 * Call this in app.whenReady() before creating any windows.
 *
 * Returns true if this is the primary instance (should continue),
 * false if a duplicate instance was detected (should quit).
 */
export function initSingleInstanceLock(): boolean {
  const gotTheLock = app.requestSingleInstanceLock();

  if (!gotTheLock) {
    // Another instance is running - quit this one
    return false;
  }

  // When another instance is launched, focus this window
  app.on("second-instance", (_event, _commandLine, _workingDirectory) => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.show();
      mainWindow.focus();
    }
  });

  return true;
}

/**
 * Set the main window reference for focus-on-second-instance.
 */
export function setMainWindow(window: BrowserWindow): void {
  mainWindow = window;
}

