"""
DASH Watchdog — Monitors all DASH services and auto-restarts on crash.

Services monitored:
  1. Ollama (AI inference)
  2. Cloudflare tunnel (Ollama → Cloud)
  3. Auto-connect (PC → Cloud registration)

Runs forever. Auto-starts with Windows via Task Scheduler.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

LOG_DIR = Path.home() / ".dash" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "watchdog.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("watchdog")

CHECK_INTERVAL = 30  # seconds between checks
OLLAMA_PORT = 11434
MAX_RESTARTS = 5  # max restarts before cooldown
COOLDOWN_SECONDS = 300  # 5 minutes cooldown after max restarts

# ============================================================
# Service Definitions
# ============================================================

class Service:
    def __init__(self, name, check_func, start_func, max_restarts=MAX_RESTARTS):
        self.name = name
        self.check_func = check_func
        self.start_func = start_func
        self.max_restarts = max_restarts
        self.restart_count = 0
        self.last_restart = 0
        self.cooldown_until = 0
        self.running = True

    def is_alive(self):
        """Check if the service is running."""
        try:
            return self.check_func()
        except Exception as e:
            log.error(f"Health check failed for {self.name}: {e}")
            return False

    def restart(self):
        """Restart the service."""
        now = time.time()

        # Check cooldown
        if now < self.cooldown_until:
            remaining = int(self.cooldown_until - now)
            log.warning(f"{self.name} in cooldown, {remaining}s remaining")
            return False

        # Check restart limit
        if self.restart_count >= self.max_restarts:
            log.warning(f"{self.name} hit max restarts ({self.max_restarts}), cooling down")
            self.cooldown_until = now + COOLDOWN_SECONDS
            self.restart_count = 0
            return False

        log.info(f"Restarting {self.name} (attempt {self.restart_count + 1})")
        try:
            self.start_func()
            self.restart_count += 1
            self.last_restart = now
            log.info(f"{self.name} restart initiated")
            return True
        except Exception as e:
            log.error(f"Failed to restart {self.name}: {e}")
            return False


# ============================================================
# Health Checks
# ============================================================

def check_ollama():
    """Check if Ollama is responding."""
    try:
        req = urllib.request.urlopen(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=5)
        return req.status == 200
    except Exception:
        return False


def check_tunnel():
    """Check if cloudflared tunnel process is running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
            capture_output=True, text=True, timeout=5
        )
        return "cloudflared.exe" in result.stdout
    except Exception:
        return False


def check_auto_connect():
    """Check if auto-connect process is running."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq python.exe"],
            capture_output=True, text=True, timeout=5
        )
        # Check for auto-connect in command line
        return "auto-connect" in result.stdout.lower()
    except Exception:
        return False


# ============================================================
# Service Starters
# ============================================================

def start_ollama():
    """Start Ollama server."""
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(3)


def start_tunnel():
    """Start Cloudflare tunnel for Ollama."""
    log_path = LOG_DIR / "tunnel.log"
    subprocess.Popen(
        ["cloudflared", "tunnel", "--url", f"http://localhost:{OLLAMA_PORT}"],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(5)


def start_auto_connect():
    """Start auto-connect script."""
    scripts_dir = Path.home() / ".dash" / "scripts"
    log_path = LOG_DIR / "auto-connect.log"
    subprocess.Popen(
        [sys.executable, str(scripts_dir / "auto-connect.py")],
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    time.sleep(3)


# ============================================================
# Main Watchdog Loop
# ============================================================

def main():
    print("╔══════════════════════════════════════════╗")
    print("║   DASH Watchdog                         ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print("Monitoring services:")
    print("  1. Ollama (AI inference)")
    print("  2. Cloudflare tunnel (Ollama → Cloud)")
    print("  3. Auto-connect (PC → Cloud)")
    print()
    print(f"Checking every {CHECK_INTERVAL}s")
    print(f"Max restarts: {MAX_RESTARTS} per {COOLDOWN_SECONDS}s")
    print(f"Logs: {LOG_DIR}")
    print()
    print("Press Ctrl+C to stop")
    print()

    # Define services
    services = [
        Service("Ollama", check_ollama, start_ollama),
        Service("Cloudflare-Tunnel", check_tunnel, start_tunnel, max_restarts=3),
        Service("Auto-Connect", check_auto_connect, start_auto_connect),
    ]

    # Handle shutdown
    running = True
    def shutdown(sig, frame):
        nonlocal running
        print("\nShutting down watchdog...")
        running = False
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Main loop
    while running:
        for service in services:
            if not service.is_alive():
                log.warning(f"{service.name} is DOWN")
                service.restart()
            else:
                # Reset restart count on successful health check
                if service.restart_count > 0:
                    log.info(f"{service.name} recovered, resetting restart count")
                    service.restart_count = 0

        # Sleep
        for _ in range(CHECK_INTERVAL):
            if not running:
                break
            time.sleep(1)

    log.info("Watchdog stopped")


if __name__ == "__main__":
    main()
