"""Ollama Tunnel Proxy — Remote Ollama access through Cloudflare tunnel.

When the Android app is on the same network as the PC, it connects directly
to http://192.168.1.x:11434. When remote, it uses this endpoint which
proxies through the Cloudflare tunnel.

The tunnel URL changes on each restart of cloudflared. This route reads
the current URL from DynamoDB so it always knows where to connect.
"""

from __future__ import annotations
import asyncio

import json
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ollama-tunnel", tags=["ollama-tunnel"])

# Default tunnel URL — updated dynamically from DynamoDB
_tunnel_url: str = ""


def set_tunnel_url(url: str):
    """Set the current tunnel URL (called when tunnel restarts)."""
    global _tunnel_url
    _tunnel_url = url
    logger.info(f"Ollama tunnel URL updated: {url}")


def get_tunnel_url() -> str:
    """Get the current tunnel URL."""
    return _tunnel_url


class TunnelChatRequest(BaseModel):
    model: str = "llama3.2:1b"
    messages: list[dict[str, str]] = []
    stream: bool = False


@router.get("/status")
async def tunnel_status() -> dict[str, Any]:
    """Check if the Cloudflare tunnel is reachable."""
    global _tunnel_url

    # Try to load from DynamoDB if not set
    if not _tunnel_url:
        try:
            def _load_from_dynamo():
                import boto3
                dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
                table = dynamodb.Table("dash-device-states")
                resp = table.get_item(Key={"device_id": "shadow"})
                return resp.get("Item", {}).get("tunnel_url", "")
            _tunnel_url = await asyncio.to_thread(_load_from_dynamo)
        except Exception:
            pass

    if not _tunnel_url:
        return {"available": False, "tunnel_url": "", "error": "No tunnel URL configured"}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{_tunnel_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = [m["name"] for m in data.get("models", [])]
                return {
                    "available": True,
                    "tunnel_url": _tunnel_url,
                    "models": models,
                    "model_count": len(models),
                }
            # 403 = Cloudflare bot protection active (tunnel is working)
            if resp.status_code == 403:
                return {
                    "available": True,
                    "tunnel_url": _tunnel_url,
                    "protected": True,
                    "note": "Cloudflare bot protection active. Use /api/v1/ollama/* for direct access.",
                }
            return {"available": False, "tunnel_url": _tunnel_url, "status_code": resp.status_code}
    except Exception as e:
        return {"available": False, "tunnel_url": _tunnel_url, "error": str(e)}


@router.get("/models")
async def tunnel_models() -> dict[str, Any]:
    """List Ollama models through the tunnel."""
    global _tunnel_url
    if not _tunnel_url:
        raise HTTPException(503, "No tunnel URL configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_tunnel_url}/api/tags")
        if resp.status_code != 200:
            raise HTTPException(502, f"Tunnel returned {resp.status_code}")
        return resp.json()


@router.post("/chat")
async def tunnel_chat(req: TunnelChatRequest) -> dict[str, Any]:
    """Chat with Ollama through the tunnel."""
    global _tunnel_url
    if not _tunnel_url:
        raise HTTPException(503, "No tunnel URL configured")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{_tunnel_url}/api/chat",
            json={
                "model": req.model,
                "messages": req.messages,
                "stream": req.stream,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"Tunnel returned {resp.status_code}")
        return resp.json()


@router.post("/set-url")
async def set_tunnel_url_endpoint(url: str) -> dict[str, Any]:
    """Update the tunnel URL (called when cloudflared restarts)."""
    set_tunnel_url(url)

    # Save to DynamoDB
    try:
        def _save_to_dynamo():
            import boto3
            from datetime import datetime, timezone
            dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
            table = dynamodb.Table("dash-device-states")
            table.update_item(
                Key={"device_id": "shadow"},
                UpdateExpression="SET tunnel_url = :url, updated_at = :now",
                ExpressionAttributeValues={
                    ":url": url,
                    ":now": datetime.now(timezone.utc).isoformat(),
                },
            )
        await asyncio.to_thread(_save_to_dynamo)
    except Exception as e:
        logger.warning(f"Failed to save tunnel URL to DynamoDB: {e}")

    return {"ok": True, "tunnel_url": url}
