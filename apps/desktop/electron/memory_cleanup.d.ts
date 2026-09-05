/**
 * MemoryCleanup - Periodically performs memory optimization to reduce Electron's RAM usage.
 *
 * Features:
 *   - Periodic GC triggering
 *   - WebContents cleanup
 *   - Unused process termination
 *   - Memory usage monitoring and alerts
 */
/**
 * Start periodic memory cleanup.
 */
export declare function startMemoryCleanup(): void;
/**
 * Stop periodic memory cleanup.
 */
export declare function stopMemoryCleanup(): void;
/**
 * Perform one round of memory cleanup.
 */
export declare function performCleanup(): void;
/**
 * Get current memory stats.
 */
export declare function getMemoryStats(): {
    heapUsedMB: number;
    heapTotalMB: number;
    rssMB: number;
};
