"""
DASH PC Auto-Connect
Runs on your PC and:
1. Registers with the cloud backend (tells it you're online)
2. Starts Ollama tunnel (exposes local AI to cloud)
3. Starts desktop control tunnel
4. Heartbeat: keeps registration alive
5. Auto-reconnects if connection drops

Run at startup or manually: python pc-auto-connect.py
"""

import os
import sys
import json
import time
import socket
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    print("Installing requests...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# ============================================================
# Configuration
# ============================================================

# Cloud backend URL (set this to your EC2/Vercel/Supabase URL)
CLOUD_BACKEND_URL = os.environ.get("DASH_CLOUD_URL", "http://YOUR_EC2_IP:8000")

# Your device token (from DASH identity.json)
IDENTITY_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "DASH" / "identity.json"

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 30

# Tunnel ports
OLLAMA_PORT = 11434
DESKTOP_CONTROL_PORT = 8000

# Log file
LOG_DIR = Path.home() / ".dash" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "auto-connect.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("auto-connect")

# ============================================================
# Device Registration
# ============================================================

def get_device_token():
    """Load device token from DASH identity file."""
    if IDENTITY_PATH.exists():
        try:
            with open(IDENTITY_PATH) as f:
                data = json.load(f)
                return data.get("token", "")
        except Exception:
            pass
    return ""


def get_local_ip():
    """Get the local IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def register_with_cloud():
    """Register this PC with the cloud backend."""
    token = get_device_token()
    local_ip = get_local_ip()

    payload = {
        "name": socket.gethostname(),
        "type": "desktop",
        "token": token,
        "local_ip": local_ip,
        "status": "online",
        "capabilities": [
            "ollama",
            "desktop_control",
            "screenshot",
            "mouse_keyboard",
            "file_access",
        ],
        "ollama_port": OLLAMA_PORT,
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        resp = requests.post(
            f"{CLOUD_BACKEND_URL}/api/v1/companion/register",
            json=payload,
            timeout=10,
            headers={"Authorization": f"Bearer {token}"},
        )
        if resp.status_code == 200:
            log.info(f"Registered with cloud: {resp.json()}")
            return True
        else:
            log.warning(f"Registration failed: {resp.status_code} {resp.text}")
            return False
    except requests.ConnectionError:
        log.warning("Cloud backend unreachable")
        return False
    except Exception as e:
        log.error(f"Registration error: {e}")
        return False


def send_heartbeat():
    """Send heartbeat to cloud backend."""
    token = get_device_token()
    try:
        resp = requests.post(
            f"{CLOUD_BACKEND_URL}/api/v1/companion/heartbeat",
            json={"status": "online", "timestamp": datetime.utcnow().isoformat()},
            timeout=5,
            headers={"Authorization": f"Bearer {token}"},
        )
        return resp.status_code == 200
    except Exception:
        return False


# ============================================================
# Tunnel Management
# ============================================================

def start_ollama_tunnel():
    """Start Cloudflare tunnel for Ollama."""
    try:
        # Check if Ollama is running
        resp = requests.get(f"http://localhost:{OLLAMA_PORT}/api/tags", timeout=3)
        if resp.status_code != 200:
            log.warning("Ollama not responding, skipping tunnel")
            return None
    except Exception:
        log.warning("Ollama not running, skipping tunnel")
        return None

    try:
        # Start cloudflared tunnel
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{OLLAMA_PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Read URL from output
        url = None
        for line in proc.stderr:
            if "trycloudflare.com" in line:
                url = line.strip().split("|")[-1].strip()
                log.info(f"Ollama tunnel started: {url}")
                # Register tunnel URL with cloud
                register_tunnel_url("ollama", url)
                break

        return proc
    except FileNotFoundError:
        log.warning("cloudflared not installed. Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")
        return None


def register_tunnel_url(service, url):
    """Register a tunnel URL with the cloud backend."""
    token = get_device_token()
    try:
        requests.post(
            f"{CLOUD_BACKEND_URL}/api/v1/companion/tunnel",
            json={"service": service, "url": url},
            timeout=5,
            headers={"Authorization": f"Bearer {token}"},
        )
        log.info(f"Registered tunnel: {service} -> {url}")
    except Exception as e:
        log.error(f"Failed to register tunnel: {e}")


# ============================================================
# Main Loop
# ============================================================

def main():
    print("╔══════════════════════════════════════════╗")
    print("║   DASH PC Auto-Connect                  ║")
    print("╚══════════════════════════════════════════╝")
    print()
    print(f"Cloud backend: {CLOUD_BACKEND_URL}")
    print(f"Device token: {'found' if get_device_token() else 'NOT FOUND'}")
    print(f"Local IP: {get_local_ip()}")
    print()

    # Start Ollama tunnel
    print("Starting Ollama tunnel...")
    ollama_tunnel = start_ollama_tunnel()

    # Register with cloud
    print("Registering with cloud backend...")
    if register_with_cloud():
        print("✓ Registered with cloud")
    else:
        print("✗ Could not reach cloud backend (will retry)")

    print()
    print("Running... Press Ctrl+C to stop")
    print(f"Heartbeat every {HEARTBEAT_INTERVAL}s")
    print()

    try:
        while True:
            time.sleep(HEARTBEAT_INTERVAL)

            # Send heartbeat
            if send_heartbeat():
                log.debug("Heartbeat sent")
            else:
                log.warning("Heartbeat failed, retrying registration...")
                register_with_cloud()

    except KeyboardInterrupt:
        print("\nShutting down...")
        if ollama_tunnel:
            ollama_tunnel.terminate()
        log.info("Auto-connect stopped")


if __name__ == "__main__":
    main()
