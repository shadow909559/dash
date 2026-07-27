/**
 * BackendManager - Manages the Python backend process lifecycle.
 *
 * Starts the backend as a child process when Electron launches.
 * Monitors health via HTTP pings.
 * Auto-restarts on crash.
 * Graceful shutdown on app quit.
 */
export declare class BackendManager {
    private process;
    private healthTimer;
    private restartAttempts;
    private stopping;
    private pythonPath;
    private backendDir;
    constructor();
    start(): Promise<void>;
    private startProcess;
    private scheduleRestart;
    private startHealthCheck;
    stop(): Promise<void>;
    getPort(): number;
    isRunning(): boolean;
}
