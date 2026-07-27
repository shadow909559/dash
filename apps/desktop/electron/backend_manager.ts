/**
 * BackendManager - Manages the Python backend process lifecycle.
 *
 * Starts the backend as a child process when Electron launches.
 * Monitors health via HTTP pings.
 * Auto-restarts on crash.
 * Graceful shutdown on app quit.
 */

import { app } from "electron";
import { ChildProcess, spawn } from "node:child_process";
import path from "node:path";
import fs from "node:fs";
import http from "node:http";

const BACKEND_PORT = 8000;
const HEALTH_CHECK_INTERVAL = 5000;
const MAX_RESTART_ATTEMPTS = 5;
const RESTART_BACKOFF_MS = 2000;

export class BackendManager {
  private process: ChildProcess | null = null;
  private healthTimer: ReturnType<typeof setInterval> | null = null;
  private restartAttempts = 0;
  private stopping = false;
  private pythonPath: string;
  private backendDir: string;

  constructor() {
    // Determine Python path
    this.pythonPath = "python";
    if (process.platform === "win32") {
      // Try common Python paths
      const candidates = [
        "python",
        "python3",
        path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Python312", "python.exe"),
        path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Python311", "python.exe"),
        "C:\\Python312\\python.exe",
        "C:\\Python311\\python.exe",
      ];
      for (const candidate of candidates) {
        try {
          if (fs.existsSync(candidate) || candidate === "python" || candidate === "python3") {
            this.pythonPath = candidate;
            break;
          }
        } catch {
          continue;
        }
      }
    }

    // Backend directory is alongside the Electron app
    if (app.isPackaged) {
      this.backendDir = path.join(app.getAppPath(), "backend");
    } else {
      this.backendDir = path.join(app.getAppPath(), "..", "..", "apps", "backend");
    }
  }

  async start(): Promise<void> {
    console.log(`[BackendManager] Starting backend from ${this.backendDir}`);
    console.log(`[BackendManager] Python: ${this.pythonPath}`);

    this.startProcess();
    this.startHealthCheck();
  }

  private startProcess(): void {
    if (this.stopping) return;

    const env = {
      ...process.env,
      DASH_BACKEND_PORT: String(BACKEND_PORT),
      DASH_ENV: app.isPackaged ? "production" : "development",
      PYTHONUNBUFFERED: "1",
    };

    try {
      this.process = spawn(this.pythonPath, ["-m", "uvicorn", "dash_backend.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT), "--log-level", "info"], {
        cwd: this.backendDir,
        env,
        stdio: ["ignore", "pipe", "pipe"],
        windowsHide: true,
      });

      this.process.stdout?.on("data", (data: Buffer) => {
        console.log(`[Backend] ${data.toString().trim()}`);
      });

      this.process.stderr?.on("data", (data: Buffer) => {
        console.error(`[Backend ERR] ${data.toString().trim()}`);
      });

      this.process.on("exit", (code: number | null) => {
        console.log(`[BackendManager] Process exited with code ${code}`);
        this.process = null;
        if (!this.stopping) {
          this.scheduleRestart();
        }
      });

      this.process.on("error", (err: Error) => {
        console.error(`[BackendManager] Process error: ${err.message}`);
        this.process = null;
        if (!this.stopping) {
          this.scheduleRestart();
        }
      });

      this.restartAttempts = 0;
      console.log("[BackendManager] Backend process started");
    } catch (err) {
      console.error("[BackendManager] Failed to start backend:", err);
      this.scheduleRestart();
    }
  }

  private scheduleRestart(): void {
    if (this.stopping) return;
    if (this.restartAttempts >= MAX_RESTART_ATTEMPTS) {
      console.error("[BackendManager] Max restart attempts reached. Giving up.");
      return;
    }

    this.restartAttempts++;
    const delay = RESTART_BACKOFF_MS * Math.pow(2, this.restartAttempts - 1);
    console.log(`[BackendManager] Restarting in ${delay}ms (attempt ${this.restartAttempts}/${MAX_RESTART_ATTEMPTS})`);

    setTimeout(() => {
      if (!this.stopping) {
        this.startProcess();
      }
    }, delay);
  }

  private startHealthCheck(): void {
    this.healthTimer = setInterval(() => {
      if (this.stopping) return;

      const req = http.get(`http://127.0.0.1:${BACKEND_PORT}/health`, (res) => {
        if (res.statusCode !== 200 && !this.stopping) {
          console.warn(`[BackendManager] Health check returned ${res.statusCode}`);
        }
      });

      req.on("error", () => {
        if (!this.stopping && !this.process) {
          console.warn("[BackendManager] Backend not responding, restarting...");
          this.startProcess();
        }
      });

      req.setTimeout(3000, () => {
        req.destroy();
      });
    }, HEALTH_CHECK_INTERVAL);
  }

  async stop(): Promise<void> {
    this.stopping = true;

    if (this.healthTimer) {
      clearInterval(this.healthTimer);
      this.healthTimer = null;
    }

    if (this.process) {
      console.log("[BackendManager] Stopping backend...");
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          console.warn("[BackendManager] Force killing backend");
          this.process?.kill("SIGKILL");
          resolve();
        }, 5000);

        this.process!.on("exit", () => {
          clearTimeout(timeout);
          resolve();
        });

        // Graceful shutdown
        if (process.platform === "win32") {
          spawn("taskkill", ["/pid", String(this.process!.pid), "/f", "/t"]);
        } else {
          this.process!.kill("SIGTERM");
        }
      });
    }
  }

  getPort(): number {
    return BACKEND_PORT;
  }

  isRunning(): boolean {
    return this.process !== null && !this.process.killed;
  }
}