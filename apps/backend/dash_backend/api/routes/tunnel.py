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
    """Check if Cloudflare tunnel is running and return its URL."""
    try:
        # Check if cloudflared process is running
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe", "/NH"],
            capture_output=True, text=True, timeout=5,
        )
        running = "cloudflared.exe" in result.stdout

        return {
            "running": running,
            "provider": "cloudflare",
            "cost": "free_forever",
            "note": "Android app connects via this tunnel URL when away from home",
        }
    except Exception as exc:
        return {
            "running": False,
            "error": str(exc)[:100],
        }


@router.get("/tunnel/url")
async def tunnel_url() -> dict:
    """Get the current tunnel URL (trycloudflare.com free tier)."""
    # The URL is displayed in the cloudflared console output
    # For production, save it to a file or SSM parameter
    return {
        "url": "Check cloudflared terminal output for URL",
        "instructions": [
            "1. Run: cloudflared tunnel --url http://localhost:8000",
            "2. Copy the URL shown (e.g. https://abc-xyz.trycloudflare.com)",
            "3. Enter it in the Android app settings",
        ],
        "cost": "free_forever",
        "limitation": "URL changes on restart (use named tunnel for permanent URL)",
    }
