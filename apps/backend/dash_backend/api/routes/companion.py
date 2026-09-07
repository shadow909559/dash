"""Companion Hub REST API routes.

Lets the desktop discover and query connected Android companions, and lets a
companion register/heartbeat. Additive — existing /phone ADB routes untouched.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user
from dash_backend.companion.hub import get_companion_hub
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/companion", tags=["companion"], dependencies=[Depends(get_current_user)])


class RegisterRequest(BaseModel):
    device_id: str = Field(..., description="Unique companion device id")
    name: str = "DASH Companion"
    transport: str = "wifi"
    host: str = ""
    platform: str = "android"
    capabilities: List[str] = Field(default_factory=list)


class HeartbeatRequest(BaseModel):
    device_id: str = Field(..., description="Companion device id")
    state: Dict[str, Any] = Field(default_factory=dict)


class CommandRequest(BaseModel):
    device_id: str = Field(..., description="Companion device id")
    action: str = Field(..., description="Action to route (e.g. open_app, read_notifications)")
    payload: Dict[str, Any] = Field(default_factory=dict)


@router.get("/devices")
async def list_companions(alive_only: bool = False) -> Dict[str, Any]:
    """List registered companion devices."""
    hub = get_companion_hub()
    devices = hub.list_alive() if alive_only else hub.list_devices()
    return {
        "devices": [d.to_dict() for d in devices],
        "count": len(devices),
    }


@router.post("/register")
async def register_companion(req: RegisterRequest) -> Dict[str, Any]:
    """Register (or update) a companion device."""
    hub = get_companion_hub()
    device = hub.register(
        req.device_id,
        name=req.name,
        transport=req.transport,
        host=req.host,
        platform=req.platform,
        capabilities=req.capabilities,
    )
    return {"status": "ok", "device": device.to_dict()}


@router.post("/heartbeat")
async def companion_heartbeat(req: HeartbeatRequest) -> Dict[str, Any]:
    """Companion heartbeat — updates state and last-seen."""
    hub = get_companion_hub()
    device = hub.get(req.device_id)
    if device is None:
        # Auto-register on first heartbeat.
        device = hub.register(req.device_id)
    else:
        device.touch()
    device.state = req.state
    return {"status": "ok", "last_seen": device.last_seen}


@router.post("/unregister")
async def unregister_companion(req: RegisterRequest) -> Dict[str, Any]:
    """Unregister a companion device."""
    hub = get_companion_hub()
    removed = hub.unregister(req.device_id)
    return {"status": "ok" if removed else "not_found"}


@router.post("/command")
async def companion_command(req: CommandRequest) -> Dict[str, Any]:
    """Route a command to a companion device.

    Best-effort: resolves the device and dispatches to the Android ecosystem
    agent if available, otherwise returns a routing hint.
    """
    hub = get_companion_hub()
    device = hub.get(req.device_id)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Companion '{req.device_id}' not found")

    device.touch()

    # Try to route via the Android ecosystem agent.
    try:
        from dash_backend.agents.ecosystem import get_ecosystem_state
        state = get_ecosystem_state()
        result = await state.dispatch_ecosystem_agent(
            "android",
            {"action": req.action, "device_id": req.device_id, **req.payload},
        )
        if isinstance(result, dict) and result.get("error"):
            logger.warning("[Companion] Android agent reported: %s", result.get("error"))
        elif result is not None:
            return {"status": "ok", "device": device.id, "result": result}
    except Exception as exc:
        logger.warning("[Companion] Android agent dispatch failed: %s", exc)

    return {
        "status": "routed",
        "device": device.id,
        "action": req.action,
        "note": "companion registered; phone will process via local automation",
    }
