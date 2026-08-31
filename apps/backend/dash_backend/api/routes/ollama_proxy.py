"""Ollama Proxy — lets Android chat with Ollama through the backend.

When PC is on: Android → local backend → Ollama (fast, local)
When PC is off: Android → EC2 backend → (EC2 can't reach Ollama directly,
              so the tunnel URL is returned for browser-based access)
"""

from __future__ import annotations

import os
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse, JSONResponse
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ollama", tags=["ollama-proxy"])

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
TUNNEL_URL = os.getenv("OLLAMA_TUNNEL_URL", "")

# Cache for current tunnel URL (set by auto-connect)
_current_tunnel_url: str = ""


def set_tunnel_url(url: str) -> None:
    global _current_tunnel_url
    _current_tunnel_url = url
    logger.info(f"Ollama tunnel URL updated: {url}")


def get_tunnel_url() -> str:
    return _current_tunnel_url or TUNNEL_URL


@router.get("/status")
async def ollama_status():
    """Check if Ollama is running locally and if tunnel is available."""
    local_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            local_ok = r.status_code == 200
    except Exception:
        pass

    tunnel = get_tunnel_url()

    return {
        "local_running": local_ok,
        "tunnel_url": tunnel,
        "tunnel_available": bool(tunnel),
        "ollama_url": OLLAMA_URL,
    }


@router.post("/chat")
async def ollama_chat(request: Request):
    """Proxy chat request to Ollama (or return tunnel URL if Ollama is down)."""
    body = await request.json()

    # Try local Ollama first
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=body,
            )
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass

    # Ollama is down — return tunnel URL for browser-based access
    tunnel = get_tunnel_url()
    return JSONResponse(
        status_code=503,
        content={
            "error": "Ollama not available locally",
            "tunnel_url": tunnel,
            "message": "Open the tunnel URL in a browser to access Ollama AI",
        },
    )


@router.post("/chat/stream")
async def ollama_chat_stream(request: Request):
    """Proxy streaming chat to Ollama."""
    body = await request.json()

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/chat",
                json=body,
                timeout=120,
            )
            if r.status_code == 200:
                return StreamingResponse(
                    iter([r.content]),
                    media_type="application/x-ndjson",
                )
    except Exception:
        pass

    tunnel = get_tunnel_url()
    return JSONResponse(
        status_code=503,
        content={"error": "Ollama unavailable", "tunnel_url": tunnel},
    )


@router.get("/models")
async def ollama_models():
    """List available Ollama models."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass

    return JSONResponse(status_code=503, content={"error": "Ollama unavailable"})
