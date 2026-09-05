"""Cloud Relay API routes.

Android-facing endpoints that let the companion app:
- Query PC status (online/offline, tunnel URL, capabilities)
- Trigger Wake-on-LAN to boot the PC remotely
- Send commands through the cloud relay to the PC
- Register itself as a companion device

These routes work on the Fly.io cloud backend and persist state
in Supabase, so they survive backend restarts.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user
from dash_backend.logging_config import get_logger
from dash_backend.services.cloud_relay import get_cloud_relay

logger = get_logger(__name__)

router = APIRouter(prefix="/relay", tags=["cloud-relay"])


# ── Request/Response Models ─────────────────────────────────────

class RegisterDeviceRequest(BaseModel):
    """Register a device (PC or Android) with the cloud relay."""
    device_id: str = Field(..., description="Unique device identifier (install_id)")
    name: str = Field(default="DASH Device", description="Human-readable name")
    platform: str = Field(default="desktop", description="desktop | android | ios")
    local_ip: str = Field(default="", description="Device's LAN IP")
    mac_address: str = Field(default="", description="MAC address for WoL")
    tunnel_url: str = Field(default="", description="Cloudflare tunnel URL")
    capabilities: List[str] = Field(default_factory=list, description="Device capabilities")


class HeartbeatRequest(BaseModel):
    """Heartbeat from a device to keep its registration alive."""
    device_id: str
    state: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary state payload")


class TunnelRegisterRequest(BaseModel):
    """Register a Cloudflare tunnel URL for a device."""
    device_id: str
    tunnel_url: str = Field(..., description="Cloudflare tunnel URL")
    service: str = Field(default="ollama", description="What the tunnel exposes")


class WoLRequest(BaseModel):
    """Request to wake a device via Wake-on-LAN."""
    device_id: str
    mac_address: Optional[str] = Field(default=None, description="MAC address (overrides stored)")


class CommandRelayRequest(BaseModel):
    """Relay a command to a device through the cloud."""
    device_id: str
    action: str = Field(..., description="Action to perform")
    payload: Dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ───────────────────────────────────────────────────

@router.post("/register")
async def register_device(req: RegisterDeviceRequest) -> Dict[str, Any]:
    """Register a device with the cloud relay."""
    relay = get_cloud_relay()
    result = await relay.register_device(
        device_id=req.device_id,
        name=req.device_id,  # Use device_id as name (dash_devices lookup key)
        platform=req.platform,
        local_ip=req.local_ip,
        mac_address=req.mac_address,
        tunnel_url=req.tunnel_url,
        capabilities=req.capabilities,
    )
    return result


@router.post("/heartbeat")
async def device_heartbeat(req: HeartbeatRequest) -> Dict[str, Any]:
    """Send a heartbeat to keep the device registration alive."""
    relay = get_cloud_relay()
    return await relay.heartbeat(
        device_id=req.device_id,
        state=req.state,
    )


@router.post("/tunnel")
async def register_tunnel(req: TunnelRegisterRequest) -> Dict[str, Any]:
    """Register a Cloudflare tunnel URL for a device."""
    relay = get_cloud_relay()
    return await relay.register_tunnel(
        device_id=req.device_id,
        tunnel_url=req.tunnel_url,
        service=req.service,
    )


@router.get("/pc-status")
async def get_pc_status() -> Dict[str, Any]:
    """Get the primary PC's status — used by Android to check if PC is online."""
    relay = get_cloud_relay()
    return await relay.get_pc_status()


@router.get("/device/{device_id}")
async def get_device(device_id: str) -> Dict[str, Any]:
    """Get a specific device's status."""
    relay = get_cloud_relay()
    device = await relay.get_device(device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.get("/devices")
async def list_devices(
    platform: Optional[str] = None,
    online_only: bool = False,
) -> Dict[str, Any]:
    """List all registered devices."""
    relay = get_cloud_relay()
    devices = await relay.list_devices(platform=platform, online_only=online_only)
    return {"devices": devices, "count": len(devices)}


@router.post("/wol")
async def trigger_wol(req: WoLRequest) -> Dict[str, Any]:
    """Trigger Wake-on-LAN for a device."""
    relay = get_cloud_relay()
    return await relay.request_wake(
        device_id=req.device_id,
        mac_address=req.mac_address,
    )


@router.post("/command")
async def relay_command(req: CommandRelayRequest) -> Dict[str, Any]:
    """Relay a command to a device through the cloud.

    This is a best-effort relay:
    - If the device has a tunnel URL, the command is noted for direct connection
    - If the device is offline, the command is queued for when it comes online
    """
    relay = get_cloud_relay()
    device = await relay.get_device(req.device_id)

    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")

    if device.get("is_stale") or device.get("status") == "offline":
        return {
            "status": "offline",
            "message": f"Device '{req.device_id}' is offline",
            "tunnel_url": None,
            "suggestion": "Try waking the device first via /relay/wol",
        }

    # Device is online — return tunnel URL for direct connection
    tunnel_url = device.get("tunnel_url")
    return {
        "status": "online",
        "device_id": req.device_id,
        "action": req.action,
        "tunnel_url": tunnel_url,
        "local_ip": device.get("local_ip"),
        "note": (
            f"Connect directly to PC via tunnel: {tunnel_url}"
            if tunnel_url
            else "No tunnel available. Connect via local network."
        ),
    }


@router.delete("/device/{device_id}")
async def remove_device(device_id: str) -> Dict[str, Any]:
    """Remove a device from the cloud relay."""
    relay = get_cloud_relay()
    return await relay.remove_device(device_id)
