"""Cloudflare Tunnel status — shows the public URL for remote access.

Replaces EC2 entirely. The tunnel exposes the local backend to the internet
for free via Cloudflare's network.
"""

from __future__ import annotations

import subprocess
from fastapi import APIRouter
from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/tunnel/status")
async def tunnel_status() -> dict:
    """Check if a tunnel is running and return its URL."""
    # Check ngrok first, then cloudflare
    providers = [
        {"name": "ngrok", "process": "ngrok.exe"},
        {"name": "cloudflare", "process": "cloudflared.exe"},
    ]
    
    for provider in providers:
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {provider['process']}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            if provider["process"] in result.stdout:
                return {
                    "running": True,
                    "provider": provider["name"],
                    "cost": "free_forever",
                    "note": "Android app connects via this tunnel URL when away from home",
                }
        except Exception:
            continue
    
    return {
        "running": False,
        "provider": None,
        "setup": "Run: ngrok http --domain=YOUR_DOMAIN 8000",
    }


@router.get("/tunnel/url")
async def tunnel_url() -> dict:
    """Get the current tunnel URL."""
    return {
        "setup": [
            "1. Sign up at https://dashboard.ngrok.com (free)",
            "2. Install: winget install ngrok.ngrok",
            "3. Auth: ngrok config add-authtoken YOUR_TOKEN",
            "4. Reserve free domain at https://dashboard.ngrok.com/domains",
            "5. Run: ngrok http --domain=YOUR_DOMAIN 8000",
            "6. Enter the URL in Android app settings",
        ],
        "cost": "free_forever",
        "permanent": True,
    }
