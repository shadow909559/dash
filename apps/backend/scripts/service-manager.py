"""
DASH Service Manager
Start, stop, restart, and check status of all DASH services.

Usage:
  python service-manager.py start     — Start all services
  python service-manager.py stop      — Stop all services
  python service-manager.py restart   — Restart all services
  python service-manager.py status    — Show status of all services
  python service-manager.py install   — Install auto-start tasks
  python service-manager.py uninstall — Remove auto-start tasks
"""

import os
import sys
import time
import subprocess
import json
from pathlib import Path
from datetime import datetime

# ============================================================
# Configuration
# ============================================================

SERVICES = {
    "ollama": {
        "name": "Ollama (AI)",
        "check": "tasklist /FI \"IMAGENAME eq ollama.exe\"",
        "start": "ollama serve",
        "stop": "taskkill /F /IM ollama.exe",
        "task_name": "DASH-Ollama",
    },
    "tunnel": {
        "name": "Cloudflare Tunnel",
        "check": "tasklist /FI \"IMAGENAME eq cloudflared.exe\"",
        "start": "cloudflared tunnel --url http://localhost:11434",
        "stop": "taskkill /F /IM cloudflared.exe",
        "task_name": "DASH-Ollama-Tunnel",
    },
    "autoconnect": {
        "name": "Auto-Connect",
        "check": "tasklist /FI \"IMAGENAME eq python.exe\"",
        "start": f"python {Path.home() / '.dash' / 'scripts' / 'auto-connect.py'}",
        "stop": None,  # Graceful shutdown via signal
        "task_name": "DASH-AutoConnect",
    },
    "watchdog": {
        "name": "Watchdog",
        "check": "tasklist /FI \"IMAGENAME eq python.exe\"",
        "start": f"python {Path.home() / '.dash' / 'scripts' / 'watchdog.py'}",
        "stop": None,
        "task_name": "DASH-Watchdog",
    },
}


def is_running(service_id):
    """Check if a service is running."""
    config = SERVICES[service_id]
    try:
        result = subprocess.run(
            config["check"],
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if service_id == "autoconnect":
            return "auto-connect" in result.stdout.lower()
        if service_id == "watchdog":
            return "watchdog" in result.stdout.lower()
        return config["name"].split("(")[0].strip().lower().replace(" ", "") in result.stdout.lower() or \
               service_id in result.stdout.lower()
    except Exception:
        return False


def start_service(service_id):
    """Start a service."""
    config = SERVICES[service_id]
    if is_running(service_id):
        print(f"  ✓ {config['name']} already running")
        return True

    try:
        subprocess.Popen(
            config["start"],
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        time.sleep(2)
        if is_running(service_id):
            print(f"  ✓ {config['name']} started")
            return True
        else:
            print(f"  ⚠ {config['name']} started but may not be responding yet")
            return True
    except Exception as e:
        print(f"  ✗ {config['name']} failed to start: {e}")
        return False


def stop_service(service_id):
    """Stop a service."""
    config = SERVICES[service_id]
    if not is_running(service_id):
        print(f"  ○ {config['name']} not running")
        return True

    if config["stop"]:
        try:
            subprocess.run(config["stop"], shell=True, timeout=5)
            time.sleep(1)
            print(f"  ✓ {config['name']} stopped")
            return True
        except Exception as e:
            print(f"  ✗ {config['name']} failed to stop: {e}")
            return False
    else:
        print(f"  ○ {config['name']} uses graceful shutdown (may take a moment)")
        return True


def show_status():
    """Show status of all services."""
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   DASH Service Status                   ║")
    print("╚══════════════════════════════════════════╝")
    print()

    for service_id, config in SERVICES.items():
        running = is_running(service_id)
        status = "● RUNNING" if running else "○ STOPPED"
        color = "✓" if running else "✗"
        print(f"  {color} {config['name']:<25} {status}")

    print()

    # Check cloud connectivity
    try:
        import urllib.request
        resp = urllib.request.urlopen("https://dash-backend.fly.dev/health", timeout=5)
        data = json.loads(resp.read())
        print(f"  ✓ Cloud Backend: {data.get('status', 'unknown')}")
    except Exception:
        print(f"  ✗ Cloud Backend: unreachable")

    # Check tunnel URL
    log_path = Path.home() / ".dash" / "logs" / "tunnel.log"
    if log_path.exists():
        try:
            with open(log_path) as f:
                for line in f:
                    if "trycloudflare.com" in line:
                        url = line.strip().split("|")[-1].strip()
                        print(f"  ✓ Tunnel URL: {url}")
                        break
        except Exception:
            pass

    print()


def install_autostart():
    """Install auto-start tasks."""
    print("Installing auto-start tasks...")
    for service_id, config in SERVICES.items():
        task_name = config["task_name"]
        start_cmd = config["start"]

        # Create batch file for the service
        batch_path = Path.home() / ".dash" / "scripts" / f"{service_id}-startup.bat"
        batch_path.parent.mkdir(parents=True, exist_ok=True)

        with open(batch_path, "w") as f:
            f.write(f"@echo off\n")
            f.write(f"timeout /t 10 /nobreak > nul\n")
            f.write(f"{start_cmd}\n")

        result = subprocess.run(
            f'schtasks /create /tn "{task_name}" /tr "{batch_path}" /sc onlogon /rl highest /f',
            shell=True,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"  ✓ {config['name']} auto-start installed")
        else:
            print(f"  ✗ {config['name']} auto-start failed: {result.stderr}")


def uninstall_autostart():
    """Remove auto-start tasks."""
    print("Removing auto-start tasks...")
    for service_id, config in SERVICES.items():
        task_name = config["task_name"]
        result = subprocess.run(
            f'schtasks /delete /tn "{task_name}" /f',
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"  ✓ {config['name']} auto-start removed")
        else:
            print(f"  ○ {config['name']} auto-start not found")


# ============================================================
# CLI
# ============================================================

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == "start":
        print("Starting all DASH services...")
        for service_id in SERVICES:
            start_service(service_id)
        print()
        show_status()

    elif command == "stop":
        print("Stopping all DASH services...")
        for service_id in reversed(list(SERVICES.keys())):
            stop_service(service_id)

    elif command == "restart":
        print("Restarting all DASH services...")
        for service_id in reversed(list(SERVICES.keys())):
            stop_service(service_id)
        time.sleep(2)
        for service_id in SERVICES:
            start_service(service_id)
        print()
        show_status()

    elif command == "status":
        show_status()

    elif command == "install":
        install_autostart()

    elif command == "uninstall":
        uninstall_autostart()

    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == "__main__":
    main()
