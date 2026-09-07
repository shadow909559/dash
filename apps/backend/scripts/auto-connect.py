"""
DASH PC Auto-Connect
Runs on your PC and:
1. Registers with the cloud backend (tells it you're online)
2. Starts Ollama tunnel (exposes local AI to cloud)
3. Heartbeat: keeps registration alive
4. Detects and registers Cloudflare tunnel URL
5. Auto-reconnects if connection drops

Run at startup or manually: python auto-connect.py
"""

import os
import re
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

# Cloud backend URL (EC2 — stop/start from phone)
CLOUD_BACKEND_URL = os.environ.get("DASH_CLOUD_URL", "http://15.206.185.189:8001")

# Your device identity (from DASH identity.json)
IDENTITY_PATH = Path(os.environ.get("LOCALAPPDATA", "")) / "DASH" / "identity.json"

# Heartbeat interval (seconds)
HEARTBEAT_INTERVAL = 30

# Tunnel ports
OLLAMA_PORT = 11434

# Log file
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "DASH" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_DIR / "auto-connect.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("auto-connect")

# Track current tunnel URL
_current_tunnel_url = ""

# ============================================================
# Device Registration
# ============================================================

def get_device_id():
    """Load device ID from DASH identity file."""
    if IDENTITY_PATH.exists():
        try:
            with open(IDENTITY_PATH) as f:
                data = json.load(f)
                return data.get("install_id", "")
        except Exception:
            pass
    return ""


def get_device_token():
    """Load device token from DASH identity file."""
    if IDENTITY_PATH.exists():
        try:
            with open(IDENTITY_PATH) as f:
                data = json.load(f)
                return data.get("device_token", "")
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


def get_mac_address():
    """Get the MAC address of this machine for WoL."""
    import uuid
    mac = uuid.getnode()
    return ":".join(f"{(mac >> (8 * i)) & 0xFF:02x}" for i in reversed(range(6)))


def register_with_cloud_relay():
    """Register this PC with the cloud relay (Supabase-backed)."""
    device_id = get_device_id()
    local_ip = get_local_ip()
    mac = get_mac_address()

    payload = {
        "device_id": device_id or socket.gethostname(),
        "name": socket.gethostname(),
        "platform": "desktop",
        "local_ip": local_ip,
        "mac_address": mac,
        "capabilities": [
            "ollama",
            "desktop_control",
            "wake_on_lan",
            "screen_share",
        ],
    }

    # Include tunnel URL if we have one
    if _current_tunnel_url:
        payload["tunnel_url"] = _current_tunnel_url

    try:
        resp = requests.post(
            f"{CLOUD_BACKEND_URL}/api/v1/relay/register",
            json=payload,
            timeout=10,
        )
        if resp.status_code == 200:
            log.info(f"Registered with cloud relay: {resp.json()}")
            return True
        else:
            log.warning(f"Cloud relay registration failed: {resp.status_code}")
            return False
    except requests.ConnectionError:
        log.warning("Cloud relay unreachable")
        return False
    except Exception as e:
        log.error(f"Cloud relay error: {e}")
        return False


def detect_tunnel_url():
    """Detect the current Cloudflare tunnel URL from cloudflared logs."""
    global _current_tunnel_url
    log_path = Path(os.environ.get("LOCALAPPDATA", "")) / "DASH" / "logs" / "tunnel.log"
    if log_path.exists():
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
            urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
            if urls:
                url = urls[-1]
                if url != _current_tunnel_url:
                    _current_tunnel_url = url
                    log.info(f"Detected tunnel URL: {url}")
                    register_tunnel_url("ollama", url)
                return url
        except Exception:
            pass
    return _current_tunnel_url


def register_tunnel_url(service, url):
    """Register a tunnel URL with cloud relay."""
    device_id = get_device_id() or socket.gethostname()
    try:
        requests.post(
            f"{CLOUD_BACKEND_URL}/api/v1/relay/tunnel",
            json={
                "device_id": device_id,
                "tunnel_url": url,
                "tunnel_service": service,
            },
            timeout=5,
        )
        log.info(f"Registered tunnel: {service} -> {url}")
    except Exception as e:
        log.error(f"Failed to register tunnel: {e}")


def send_heartbeat():
    """Send heartbeat to cloud relay and register tunnel URL."""
    device_id = get_device_id() or socket.gethostname()
    success = False

    # Detect and register current tunnel URL
    tunnel = detect_tunnel_url()

    # Heartbeat to cloud relay
    payload = {"device_id": device_id, "state": {"status": "online"}}
    if tunnel:
        payload["state"]["tunnel_url"] = tunnel
    try:
        resp = requests.post(
            f"{CLOUD_BACKEND_URL}/api/v1/relay/heartbeat",
            json=payload,
            timeout=5,
        )
        success = resp.status_code == 200
    except Exception:
        pass

    return success


# ============================================================
# Main Loop
# ============================================================

def main():
    print("=" * 50)
    print("   DASH PC Auto-Connect")
    print("=" * 50)
    print()
    print(f"Cloud backend: {CLOUD_BACKEND_URL}")
    print(f"Local IP: {get_local_ip()}")
    print(f"MAC: {get_mac_address()}")
    print()

    # Register with cloud
    print("Registering with cloud relay...")
    if register_with_cloud_relay():
        print("[OK] Registered with cloud relay")
    else:
        print("[WARN] Could not reach cloud relay (will retry)")

    # Detect existing tunnel
    tunnel = detect_tunnel_url()
    if tunnel:
        print(f"[OK] Tunnel detected: {tunnel}")
    else:
        print("[INFO] No tunnel detected yet (will auto-detect)")

    print()
    print(f"Running... Heartbeat every {HEARTBEAT_INTERVAL}s")
    print()

    try:
        while True:
            time.sleep(HEARTBEAT_INTERVAL)
            if send_heartbeat():
                log.debug("Heartbeat sent")
            else:
                log.warning("Heartbeat failed, retrying registration...")
                register_with_cloud_relay()

    except KeyboardInterrupt:
        print("\nShutting down...")
        log.info("Auto-connect stopped")


if __name__ == "__main__":
    main()
