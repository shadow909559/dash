/**
 * BackendManager — single-owner FastAPI lifecycle.
 *
 * PORT FREE: start exactly one backend.
 * PORT OCCUPIED + DASH HEALTHY: reuse, never spawn.
 * PORT OCCUPIED + stale DASH: stop that DASH process, start exactly one.
 * PORT OCCUPIED + unknown process: do not spawn (port conflict).
 *
 * All start/restart/recover work is serialized on one mutex.
 * Only the child spawned by this Electron instance is force-stopped on quit.
 */
export declare class BackendManager {
    private process;
    private healthTimer;
    private restartAttempts;
    private stopping;
    private pythonPath;
    private backendDir;
    private usePythonDirect;
    private ownedPid;
    private trackingPid;
    private ownsProcess;
    private lifecycle;
    private opChain;
    private recoverScheduled;
    private lastHealthOk;
    private unhealthyTicks;
    private lockPath;
    constructor();
    private log;
    private enqueue;
    start(): Promise<void>;
    private startExclusive;
    private waitForBackend;
    private probeDashHealth;
    private httpHealth;
    private bodyLooksLikeDash;
    private isPortInUse;
    private getListeningPid;
    private getProcessCommandLine;
    private commandLineLooksLikeDash;
    private startProcess;
    private scheduleRecover;
    private recoverExclusive;
    private startHealthCheck;
    stop(): Promise<void>;
    private stopPid;
    private clearOwnedIf;
    private writeLock;
    private clearLockIfOwned;
    private sleep;
    getPort(): number;
    isRunning(): boolean;
}
