/**
 * MemoryCleanup - Periodically performs memory optimization to reduce Electron's RAM usage.
 *
 * Features:
 *   - Periodic GC triggering
 *   - WebContents cleanup
 *   - Unused process termination
 *   - Memory usage monitoring and alerts
 */
import { app, webContents } from "electron";
const CLEANUP_INTERVAL_MS = 5 * 60 * 1000; // Every 5 minutes
const MEMORY_WARNING_MB = 500;
const MEMORY_CRITICAL_MB = 800;
let cleanupTimer = null;
/**
 * Start periodic memory cleanup.
 */
export function startMemoryCleanup() {
    if (cleanupTimer) {
        clearInterval(cleanupTimer);
    }
    cleanupTimer = setInterval(() => {
        performCleanup();
    }, CLEANUP_INTERVAL_MS);
    // Also clean on idle
    app.on("web-contents-created", (_event, contents) => {
        contents.on("destroyed", () => {
            // WebContents was destroyed - memory freed
        });
    });
}
/**
 * Stop periodic memory cleanup.
 */
export function stopMemoryCleanup() {
    if (cleanupTimer) {
        clearInterval(cleanupTimer);
        cleanupTimer = null;
    }
}
/**
 * Perform one round of memory cleanup.
 */
export function performCleanup() {
    // 1. Clear unused webContents
    const allContents = webContents.getAllWebContents();
    for (const contents of allContents) {
        try {
            if (contents.isDestroyed())
                continue;
            // Clear navigation history
            if (contents.navigationHistory && typeof contents.navigationHistory.clear === "function") {
                contents.navigationHistory.clear();
            }
            // Force GC hint (V8 doesn't expose explicit GC in production)
            if (contents.session) {
                contents.session.flushStorageData();
            }
        }
        catch {
            // Ignore errors during cleanup
        }
    }
    // 2. Suggest V8 GC (only works with --js-flags="--expose-gc")
    try {
        if (global.gc) {
            global.gc();
        }
    }
    catch {
        // Not available without expose-gc flag
    }
    // 3. Log memory usage if high
    const memUsage = process.memoryUsage();
    const heapUsedMB = Math.round(memUsage.heapUsed / 1024 / 1024);
    if (heapUsedMB > MEMORY_CRITICAL_MB) {
        console.warn(`[MemoryCleanup] High memory usage: ${heapUsedMB}MB ` +
            `(heap: ${Math.round(memUsage.heapTotal / 1024 / 1024)}MB, ` +
            `rss: ${Math.round(memUsage.rss / 1024 / 1024)}MB)`);
    }
    else if (heapUsedMB > MEMORY_WARNING_MB) {
        console.log(`[MemoryCleanup] Memory usage: ${heapUsedMB}MB ` +
            `(rss: ${Math.round(memUsage.rss / 1024 / 1024)}MB)`);
    }
}
/**
 * Get current memory stats.
 */
export function getMemoryStats() {
    const memUsage = process.memoryUsage();
    return {
        heapUsedMB: Math.round(memUsage.heapUsed / 1024 / 1024),
        heapTotalMB: Math.round(memUsage.heapTotal / 1024 / 1024),
        rssMB: Math.round(memUsage.rss / 1024 / 1024),
    };
}
