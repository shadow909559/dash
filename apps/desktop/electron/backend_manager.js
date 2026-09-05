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
import { app } from "electron";
import { spawn } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import net from "node:net";
import os from "node:os";
import path from "node:path";
const BACKEND_PORT = 8000;
const HEALTH_CHECK_INTERVAL = 15000; // Increased to 15 seconds to reduce aggressive checks
const MAX_RESTART_ATTEMPTS = 3; // Reduced to prevent excessive restart attempts
const RESTART_BACKOFF_MS = 3000; // Increased backoff for more stable recovery
// ONE canonical liveness endpoint. It is unauthenticated, cheap, and served
// directly by the FastAPI app (dash_backend.api.routes.health /health).
// Authenticated diagnostics (/health/diagnostic etc.) are intentionally NOT
// probed here — a 401 from them must never be mistaken for a dead backend.
const HEALTH_PATHS = ["/health"];
// Consecutive failed probes before an unowned-but-stale DASH instance is
// replaced (3 × 15s ≈ 45s of continuous unhealthiness).
const STALE_REPLACE_THRESHOLD = 3;
export class BackendManager {
    constructor() {
        this.process = null;
        this.healthTimer = null;
        this.restartAttempts = 0;
        this.stopping = false;
        this.usePythonDirect = false;
        this.ownedPid = null;
        this.trackingPid = null;
        this.ownsProcess = false;
        this.lifecycle = "idle";
        this.opChain = Promise.resolve();
        this.recoverScheduled = false;
        this.lastHealthOk = false;
        this.unhealthyTicks = 0;
        this.lockPath = path.join(app.getPath("userData"), "dash-backend.lock");
        if (app.isPackaged) {
            this.backendDir = path.join(app.getAppPath(), "backend");
            this.pythonPath = path.join(this.backendDir, "DashBackend.exe");
        }
        else {
            this.backendDir = path.join(app.getAppPath(), "..", "..", "apps", "backend");
            const venvPythonPath = path.join(this.backendDir, ".venv", "Scripts", "python.exe");
            if (fs.existsSync(venvPythonPath)) {
                this.pythonPath = venvPythonPath;
                console.log(`[BackendManager] Using virtual environment Python: ${this.pythonPath}`);
            }
            else {
                this.pythonPath = "python";
                console.warn(`[BackendManager] Virtual environment Python not found at ${venvPythonPath}, falling back to global Python`);
            }
            this.usePythonDirect = true;
        }
    }
    log(event, extra) {
        const payload = extra ? ` ${JSON.stringify(extra)}` : "";
        console.log(`[BackendManager] state=${this.lifecycle} ${event}${payload}`);
    }
    enqueue(op) {
        const run = this.opChain.then(op, op);
        this.opChain = run.then(() => undefined, () => undefined);
        return run;
    }
    async start() {
        return this.enqueue(() => this.startExclusive());
    }
    async startExclusive() {
        if (this.stopping) {
            this.log("start skipped — stopping");
            return;
        }
        this.lifecycle = "checking";
        this.log("checking port and health", { port: BACKEND_PORT });
        const probe = await this.probeDashHealth();
        const portInUse = await this.isPortInUse();
        const listenerPid = await this.getListeningPid();
        if (probe.ok && probe.isDash) {
            this.lifecycle = "reusing";
            this.ownsProcess = this.ownedPid != null && listenerPid === this.ownedPid;
            this.trackingPid = listenerPid;
            this.lastHealthOk = true;
            this.unhealthyTicks = 0;
            this.restartAttempts = 0; // Reset restart attempts on successful health check
            this.recoverScheduled = false; // Cancel any pending recovery
            this.writeLock(listenerPid, this.ownsProcess);
            // Log ownership evidence so "reusing" is verifiable, not assumed.
            const cmd = listenerPid ? await this.getProcessCommandLine(listenerPid) : "";
            this.log("reusing healthy DASH backend", {
                pid: listenerPid,
                owned: this.ownsProcess,
                healthPath: HEALTH_PATHS[0],
                latencyMs: probe.latencyMs,
                cmd: cmd.slice(0, 180),
            });
            this.lifecycle = "healthy";
            this.startHealthCheck();
            return;
        }
        if (portInUse) {
            const cmd = listenerPid ? await this.getProcessCommandLine(listenerPid) : "";
            const looksLikeDash = this.commandLineLooksLikeDash(cmd);
            if (looksLikeDash || (this.ownedPid != null && listenerPid === this.ownedPid)) {
                this.lifecycle = "recovering";
                this.log("stale DASH on port — cleaning up", { pid: listenerPid, cmd: cmd.slice(0, 180) });
                await this.stopPid(listenerPid, listenerPid === this.ownedPid || looksLikeDash);
                this.clearOwnedIf(listenerPid);
                await this.sleep(1200);
            }
            else {
                this.lifecycle = "blocked";
                this.log("port occupied by non-DASH process — will not spawn", {
                    pid: listenerPid,
                    cmd: cmd.slice(0, 180),
                });
                this.startHealthCheck();
                return;
            }
        }
        const stillBusy = await this.isPortInUse();
        if (stillBusy) {
            const pid = await this.getListeningPid();
            const retry = await this.probeDashHealth();
            if (retry.ok && retry.isDash) {
                this.lifecycle = "healthy";
                this.ownsProcess = false;
                this.trackingPid = pid;
                this.lastHealthOk = true;
                this.recoverScheduled = false; // Cancel any pending recovery
                this.writeLock(pid, false);
                this.log("port still occupied but DASH became healthy — reusing", { pid });
                this.startHealthCheck();
                return;
            }
            this.lifecycle = "blocked";
            this.log("cannot bind — port still occupied after cleanup", { pid });
            this.startHealthCheck();
            return;
        }
        this.lifecycle = "starting";
        this.log("port free — launching one backend");
        this.startProcess();
        try {
            await this.waitForBackend();
            this.lifecycle = "healthy";
            this.lastHealthOk = true;
            this.restartAttempts = 0;
            this.recoverScheduled = false; // Cancel any pending recovery
            this.startHealthCheck();
        }
        catch (err) {
            this.log("startup wait failed", { error: String(err) });
            const after = await this.probeDashHealth();
            if (after.ok && after.isDash) {
                this.lifecycle = "healthy";
                this.lastHealthOk = true;
                this.ownsProcess = false;
                this.recoverScheduled = false; // Cancel any pending recovery
                this.startHealthCheck();
                return;
            }
            throw err;
        }
    }
    async waitForBackend(maxAttempts = 40, interval = 500) {
        this.log("waiting for backend health");
        for (let i = 0; i < maxAttempts; i++) {
            if (this.stopping)
                return;
            const probe = await this.probeDashHealth();
            if (probe.ok && probe.isDash) {
                this.log("backend health check passed");
                return;
            }
            const childDead = this.process != null &&
                this.process.exitCode != null;
            if (childDead) {
                throw new Error(`Backend process exited with code ${this.process?.exitCode}`);
            }
            await this.sleep(interval);
        }
        throw new Error("Backend failed to start within timeout period");
    }
    probeDashHealth() {
        return (async () => {
            for (const healthPath of HEALTH_PATHS) {
                const probe = await this.httpHealth(healthPath);
                if (probe.ok)
                    return probe;
                // Log the specific failure reason for debugging
                if (probe.errorType !== "none") {
                    this.log(`health probe failed for ${healthPath}`, {
                        errorType: probe.errorType,
                        errorMessage: probe.errorMessage,
                        statusCode: probe.statusCode,
                    });
                }
            }
            return {
                ok: false,
                isDash: false,
                statusCode: null,
                bodySnippet: "",
                errorType: "connection_refused",
                errorMessage: "All health endpoints failed"
            };
        })();
    }
    httpHealth(healthPath) {
        return new Promise((resolve) => {
            const startedAt = Date.now();
            const req = http.get({
                host: "127.0.0.1",
                port: BACKEND_PORT,
                path: healthPath,
                timeout: 2000,
            }, (res) => {
                const chunks = [];
                res.on("data", (c) => {
                    if (chunks.length < 8)
                        chunks.push(c);
                });
                res.on("end", () => {
                    const body = Buffer.concat(chunks).toString("utf8");
                    const isDash = this.bodyLooksLikeDash(body);
                    const isHealthy = res.statusCode === 200 && isDash;
                    let errorType = "none";
                    let errorMessage = "";
                    if (!isHealthy) {
                        if (res.statusCode === null) {
                            errorType = "connection_refused";
                            errorMessage = "Connection refused";
                        }
                        else if (res.statusCode !== 200) {
                            errorType = "http_error";
                            errorMessage = `HTTP ${res.statusCode}`;
                        }
                        else if (!isDash) {
                            errorType = "invalid_response";
                            errorMessage = "Not a DASH backend response";
                        }
                    }
                    resolve({
                        ok: isHealthy,
                        isDash,
                        statusCode: res.statusCode ?? null,
                        bodySnippet: body.slice(0, 200),
                        errorType,
                        errorMessage,
                        latencyMs: Date.now() - startedAt,
                    });
                });
            });
            req.on("error", (err) => {
                const errorType = err.code === "ECONNREFUSED" ? "connection_refused" : "http_error";
                resolve({
                    ok: false,
                    isDash: false,
                    statusCode: null,
                    bodySnippet: "",
                    errorType,
                    errorMessage: err.message || "Connection error"
                });
            });
            req.on("timeout", () => {
                req.destroy();
                resolve({
                    ok: false,
                    isDash: false,
                    statusCode: null,
                    bodySnippet: "",
                    errorType: "timeout",
                    errorMessage: "Request timeout"
                });
            });
        });
    }
    bodyLooksLikeDash(body) {
        // Strict identity: the canonical /health payload is
        // {"status":"ok","service":"DASH Backend",...}. Anything else is not
        // accepted as proof that a DASH backend owns the port.
        try {
            const json = JSON.parse(body);
            if (json.status !== "ok")
                return false;
            const service = `${json.service ?? ""} ${json.app ?? ""}`.toLowerCase();
            return service.includes("dash");
        }
        catch {
            return false;
        }
    }
    isPortInUse() {
        return new Promise((resolve) => {
            const server = net.createServer();
            server.once("error", (err) => {
                resolve(err.code === "EADDRINUSE");
            });
            server.once("listening", () => {
                server.close(() => resolve(false));
            });
            server.listen(BACKEND_PORT, "127.0.0.1");
        });
    }
    getListeningPid() {
        return new Promise((resolve) => {
            const netstat = spawn("netstat", ["-ano", "-p", "tcp"], { windowsHide: true });
            let output = "";
            netstat.stdout?.on("data", (data) => {
                output += data.toString();
            });
            netstat.on("error", () => resolve(null));
            netstat.on("close", () => {
                const needle = `127.0.0.1:${BACKEND_PORT}`;
                const lines = output.split(/\r?\n/);
                for (const line of lines) {
                    if (!line.includes(needle))
                        continue;
                    if (!/LISTEN/i.test(line))
                        continue;
                    const parts = line.trim().split(/\s+/);
                    const pid = parseInt(parts[parts.length - 1], 10);
                    if (!Number.isNaN(pid) && pid > 0) {
                        resolve(pid);
                        return;
                    }
                }
                resolve(null);
            });
        });
    }
    getProcessCommandLine(pid) {
        return new Promise((resolve) => {
            const ps = spawn("powershell.exe", [
                "-NoProfile",
                "-Command",
                `(Get-CimInstance Win32_Process -Filter "ProcessId=${pid}").CommandLine`,
            ], { windowsHide: true });
            let output = "";
            ps.stdout?.on("data", (d) => {
                output += d.toString();
            });
            ps.on("error", () => resolve(""));
            ps.on("close", () => resolve(output.trim()));
        });
    }
    commandLineLooksLikeDash(cmd) {
        const lower = cmd.toLowerCase();
        return (lower.includes("dash_backend") ||
            lower.includes("dashbackend") ||
            lower.includes("uvicorn") ||
            lower.includes("dash-backend"));
    }
    startProcess() {
        if (this.stopping)
            return;
        if (this.process && this.process.exitCode == null) {
            this.log("spawn skipped — owned process already running", { pid: this.process.pid });
            return;
        }
        this.log("launching backend process", {
            cwd: this.backendDir,
            exe: this.pythonPath,
        });
        const env = {
            ...process.env,
            DASH_BACKEND_PORT: String(BACKEND_PORT),
            DASH_ENV: app.isPackaged ? "production" : "development",
            PYTHONUNBUFFERED: "1",
        };
        const args = this.usePythonDirect
            ? ["-m", "uvicorn", "dash_backend.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT), "--log-level", "info"]
            : [];
        if (!this.usePythonDirect && !fs.existsSync(this.pythonPath)) {
            throw new Error(`Backend executable not found: ${this.pythonPath}`);
        }
        this.process = spawn(this.pythonPath, args, {
            cwd: this.backendDir,
            env,
            stdio: ["ignore", "pipe", "pipe"],
            windowsHide: true,
            detached: false,
            shell: false,
        });
        this.ownedPid = this.process.pid ?? null;
        this.trackingPid = this.ownedPid;
        this.ownsProcess = true;
        this.writeLock(this.ownedPid, true);
        this.log("backend process started", { pid: this.ownedPid });
        this.process.stdout?.on("data", (data) => {
            console.log(`[Backend OUT] ${data.toString().trim()}`);
        });
        this.process.stderr?.on("data", (data) => {
            console.error(`[Backend ERR] ${data.toString().trim()}`);
        });
        this.process.on("exit", (code) => {
            const pid = this.process?.pid;
            this.log("backend process exited", { code, pid });
            if (this.ownedPid === pid) {
                this.process = null;
                this.ownedPid = null;
                this.ownsProcess = false;
            }
            if (!this.stopping) {
                this.scheduleRecover(`exit code ${code}`);
            }
        });
        this.process.on("error", (err) => {
            this.log("backend process error", { error: err.message });
            this.process = null;
            this.ownedPid = null;
            this.ownsProcess = false;
            if (!this.stopping) {
                this.scheduleRecover(err.message);
            }
        });
    }
    scheduleRecover(reason) {
        if (this.stopping || this.recoverScheduled)
            return;
        if (this.restartAttempts >= MAX_RESTART_ATTEMPTS) {
            this.log("max restart attempts reached — giving up", {
                attempts: this.restartAttempts,
                reason,
            });
            return;
        }
        this.recoverScheduled = true;
        this.restartAttempts += 1;
        const delay = RESTART_BACKOFF_MS * Math.pow(2, this.restartAttempts - 1);
        this.log("scheduling recover", { delay, attempt: this.restartAttempts, reason });
        setTimeout(() => {
            this.recoverScheduled = false;
            if (this.stopping)
                return;
            this.enqueue(() => this.recoverExclusive()).catch((err) => {
                this.log("recover failed", { error: String(err) });
            });
        }, delay);
    }
    async recoverExclusive() {
        if (this.stopping)
            return;
        this.lifecycle = "recovering";
        // Double-check if a healthy backend already exists
        const probe = await this.probeDashHealth();
        if (probe.ok && probe.isDash) {
            this.lifecycle = "healthy";
            this.lastHealthOk = true;
            this.restartAttempts = 0;
            this.ownsProcess = false;
            this.trackingPid = await this.getListeningPid();
            this.log("recover: healthy backend already present — not spawning");
            return;
        }
        // Check if port is occupied by another process
        const portInUse = await this.isPortInUse();
        if (portInUse) {
            const pid = await this.getListeningPid();
            const cmd = pid ? await this.getProcessCommandLine(pid) : "";
            if (this.commandLineLooksLikeDash(cmd)) {
                // A DASH backend holds the port. Never spawn a duplicate; report the
                // truth — it exists but is not answering health checks right now.
                this.lifecycle = "unhealthy";
                this.log("recover: DASH backend present on port but unhealthy — monitoring, not spawning", { pid });
                return;
            }
            else {
                this.lifecycle = "wrong_process";
                this.log("recover: non-DASH process occupies port — blocked", { pid, cmd: cmd.slice(0, 100) });
                return;
            }
        }
        // Only spawn if port is truly free
        await this.startExclusive();
    }
    startHealthCheck() {
        if (this.healthTimer) {
            clearInterval(this.healthTimer);
        }
        this.log("starting periodic health checks", { intervalMs: HEALTH_CHECK_INTERVAL });
        this.healthTimer = setInterval(() => {
            if (this.stopping)
                return;
            this.enqueue(async () => {
                if (this.stopping)
                    return;
                if (this.lifecycle === "starting" || this.lifecycle === "recovering")
                    return;
                const probe = await this.probeDashHealth();
                if (probe.ok && probe.isDash) {
                    const recovered = !this.lastHealthOk;
                    this.lastHealthOk = true;
                    this.unhealthyTicks = 0;
                    this.restartAttempts = 0;
                    this.recoverScheduled = false;
                    // "health restored" is only ever logged after a real failure.
                    if (recovered) {
                        this.log("health restored", { latencyMs: probe.latencyMs });
                    }
                    if (this.lifecycle !== "healthy") {
                        this.lifecycle = "healthy";
                    }
                    return;
                }
                // Health failed — classify truthfully. A timeout/HTTP error against a
                // DASH-looking process is UNHEALTHY, never "another instance running".
                this.lastHealthOk = false;
                this.unhealthyTicks += 1;
                const portInUse = await this.isPortInUse();
                this.log("health check failed", {
                    portInUse,
                    status: probe.statusCode,
                    errorType: probe.errorType,
                    errorMessage: probe.errorMessage,
                    consecutiveFailures: this.unhealthyTicks,
                });
                // Owned process recovery (unchanged semantics): wait for a couple of
                // consecutive failures before restarting.
                if (this.ownsProcess && this.process && this.process.exitCode == null) {
                    if (this.unhealthyTicks === 1) {
                        this.log("owned backend unhealthy — first failure, waiting for next check");
                        this.restartAttempts = 1;
                        return;
                    }
                    if (this.restartAttempts < 2) {
                        this.log(`owned backend unhealthy — attempt ${this.restartAttempts + 1}, waiting`);
                        this.restartAttempts++;
                        return;
                    }
                    this.log("owned backend unhealthy — scheduling recovery after multiple failures");
                    this.scheduleRecover("owned process unhealthy after multiple failures");
                    return;
                }
                if (!portInUse) {
                    this.lifecycle = "unhealthy";
                    this.log("backend unreachable and port free", { errorType: probe.errorType });
                    if (this.ownsProcess || this.trackingPid) {
                        this.scheduleRecover("backend unreachable");
                    }
                    else {
                        this.log("no owned backend to recover — waiting for external DASH or manual start");
                    }
                    return;
                }
                const pid = await this.getListeningPid();
                const cmd = pid ? await this.getProcessCommandLine(pid) : "";
                const looksLikeDash = this.commandLineLooksLikeDash(cmd);
                if (looksLikeDash || (this.ownedPid != null && pid === this.ownedPid)) {
                    // A DASH backend owns the port but is not answering /health.
                    if (this.unhealthyTicks >= STALE_REPLACE_THRESHOLD) {
                        this.lifecycle = "stale";
                        this.log("stale DASH backend detected — replacing with one healthy instance", { pid, cmd: cmd.slice(0, 180), consecutiveFailures: this.unhealthyTicks });
                        await this.stopPid(pid, true);
                        this.clearOwnedIf(pid);
                        this.unhealthyTicks = 0;
                        await this.sleep(1500);
                        this.scheduleRecover("stale DASH replaced");
                    }
                    else {
                        this.lifecycle = "unhealthy";
                        this.log("DASH backend on port is not answering health checks — monitoring", {
                            pid,
                            errorType: probe.errorType,
                            consecutiveFailures: this.unhealthyTicks,
                        });
                    }
                    return;
                }
                // Only now is it genuinely a foreign occupant.
                this.lifecycle = "wrong_process";
                this.log("port occupied by non-DASH process — will not spawn", {
                    pid,
                    cmd: cmd.slice(0, 180),
                });
            }).catch((err) => this.log("health tick failed", { error: String(err) }));
        }, HEALTH_CHECK_INTERVAL);
    }
    async stop() {
        this.stopping = true;
        this.lifecycle = "stopped";
        if (this.healthTimer) {
            clearInterval(this.healthTimer);
            this.healthTimer = null;
        }
        if (this.ownsProcess && this.process && this.process.pid) {
            this.log("stopping owned backend", { pid: this.process.pid });
            const child = this.process;
            await this.stopPid(child.pid, true);
            this.process = null;
            this.ownedPid = null;
            this.ownsProcess = false;
        }
        else {
            this.log("stop — no owned process (external DASH left running)");
        }
        this.clearLockIfOwned();
    }
    stopPid(pid, allowed) {
        if (!pid || !allowed)
            return Promise.resolve();
        return new Promise((resolve) => {
            if (process.platform === "win32") {
                const killer = spawn("taskkill", ["/pid", String(pid), "/t", "/f"], { windowsHide: true });
                killer.on("close", () => resolve());
                killer.on("error", () => {
                    try {
                        process.kill(pid);
                    }
                    catch {
                        /* already gone */
                    }
                    resolve();
                });
            }
            else {
                try {
                    process.kill(pid, "SIGTERM");
                }
                catch {
                    /* already gone */
                }
                resolve();
            }
        });
    }
    clearOwnedIf(pid) {
        if (pid && this.ownedPid === pid) {
            this.process = null;
            this.ownedPid = null;
            this.ownsProcess = false;
        }
    }
    writeLock(pid, owned) {
        try {
            fs.writeFileSync(this.lockPath, JSON.stringify({
                pid,
                owned,
                electronPid: process.pid,
                host: os.hostname(),
                updatedAt: Date.now(),
            }), "utf8");
        }
        catch (err) {
            this.log("failed to write lock file", { error: String(err) });
        }
    }
    clearLockIfOwned() {
        try {
            if (fs.existsSync(this.lockPath)) {
                const raw = fs.readFileSync(this.lockPath, "utf8");
                const data = JSON.parse(raw);
                if (data.electronPid === process.pid && data.owned) {
                    fs.unlinkSync(this.lockPath);
                }
            }
        }
        catch {
            /* ignore */
        }
    }
    sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }
    getPort() {
        return BACKEND_PORT;
    }
    isRunning() {
        // Truthful by definition: only an actual passing health check counts.
        // "A process object exists" is NOT proof of a working backend.
        return this.lastHealthOk;
    }
}
