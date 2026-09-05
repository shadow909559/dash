"""
REST API routes for phone integration: devices, battery, storage, network,
clipboard, flashlight, notifications, files, apps, SMS, call status, location.

Provides HTTP endpoints for phone data and control via the ADB backend.
Backend-only (no UI). Integrates with the existing DASH architecture.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user
from dash_backend.logging_config import get_logger
from dash_backend.phone.adb_service import get_adb_service

logger = get_logger(__name__)

router = APIRouter(prefix="/phone", tags=["phone"], dependencies=[Depends(get_current_user)])


def _adb() -> Any:
    """Get the global ADB service singleton."""
    return get_adb_service()


# ── Request / Response Models ────────────────────────────────


class BatteryInfo(BaseModel):
    level: int = 0
    is_charging: bool = False
    health: str = "unknown"
    temperature: float = 0.0
    voltage: float = 0.0
    technology: str = "unknown"


class StorageInfo(BaseModel):
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    used_percent: int = 0


class NetworkInfo(BaseModel):
    is_connected: bool = False
    type: str = "unknown"
    ssid: str = "unknown"
    is_metered: bool = False
    signal_strength: int = 0


class VolumeInfo(BaseModel):
    volume: int = 0
    is_muted: bool = False
    max_volume: int = 100


class PhoneState(BaseModel):
    battery: BatteryInfo = Field(default_factory=BatteryInfo)
    storage: StorageInfo = Field(default_factory=StorageInfo)
    network: NetworkInfo = Field(default_factory=NetworkInfo)
    clipboard: str = ""
    volume: VolumeInfo = Field(default_factory=VolumeInfo)
    flashlight: bool = False
    notifications_enabled: bool = True
    timestamp: float = 0.0


class ClipboardWriteRequest(BaseModel):
    text: str = Field(..., description="Text to copy to clipboard")


class VolumeSetRequest(BaseModel):
    level: int = Field(..., ge=0, le=100, description="Volume level 0-100")


class FlashlightToggleRequest(BaseModel):
    enabled: bool = Field(..., description="Flashlight state")


class StatusResponse(BaseModel):
    status: str = "ok"
    details: dict[str, Any] = Field(default_factory=dict)


class DeviceInfo(BaseModel):
    serial: str = ""
    state: str = "unknown"
    transport: str = "usb"


class WirelessConnectRequest(BaseModel):
    host: str = Field(..., description="IP address or hostname")
    port: int = Field(5555, description="Wireless ADB port")


class PushFileRequest(BaseModel):
    local_path: str = Field(..., description="Local file path")
    device_path: str = Field(..., description="Device destination path")


class SendSmsRequest(BaseModel):
    phone_number: str = Field(..., description="Recipient phone number")
    message: str = Field(..., description="SMS message body")


class OpenAppRequest(BaseModel):
    package: str = Field(..., description="Android package name")


# ── Device Discovery Endpoints ───────────────────────────────


@router.get("/devices", response_model=StatusResponse)
async def list_devices() -> StatusResponse:
    """Discover connected ADB devices (USB + wireless)."""
    try:
        service = _adb()
        devices = await service.discover_devices()
        return StatusResponse(status="ok", details={"devices": devices})
    except Exception as exc:
        logger.exception("list_devices failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/devices/connect", response_model=StatusResponse)
async def connect_wireless(req: WirelessConnectRequest) -> StatusResponse:
    """Connect to a device over wireless ADB."""
    try:
        service = _adb()
        result = await service.connect_wireless(req.host, req.port)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("connect_wireless failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/devices/disconnect", response_model=StatusResponse)
async def disconnect_wireless(req: WirelessConnectRequest) -> StatusResponse:
    """Disconnect a wireless ADB device."""
    try:
        service = _adb()
        result = await service.disconnect_wireless(req.host, req.port)
        return StatusResponse(status="ok", details={"message": result.get("summary", "")})
    except Exception as exc:
        logger.exception("disconnect_wireless failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/devices/pair", response_model=StatusResponse)
async def pair_devices(req: WirelessConnectRequest, pairing_code: str) -> StatusResponse:
    """Pair with a device for wireless ADB (Android 11+)."""
    try:
        service = _adb()
        result = await service.pair_wireless(req.host, pairing_code, req.port)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("pair_devices failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Phone Data Endpoints ─────────────────────────────────────


@router.get("/state", response_model=PhoneState)
async def get_phone_state(serial: Optional[str] = None) -> PhoneState:
    """Get current phone state (battery, storage, network, etc.).

    Prefers live ADB data; falls back to the latest snapshot reported by
    the mobile companion app (POST /phone/state).
    """
    try:
        service = _adb()
        battery = await service.get_battery(serial)
        level = 0
        charging = False
        if battery.get("ok"):
            try:
                level = int(battery.get("level", 0))
            except (TypeError, ValueError):
                level = 0
            charging = bool(battery.get("is_charging"))
        if battery.get("ok") or serial:
            return PhoneState(
                battery=BatteryInfo(level=level, is_charging=charging),
                timestamp=0.0,
            )
    except Exception as exc:
        logger.warning("get_phone_state via ADB failed: %s", exc)

    # Fall back to the latest companion-app snapshot, if any.
    try:
        from dash_backend.cache.simple_cache import get_cache

        cached = get_cache().get("phone_state_latest")
        if isinstance(cached, dict):
            return PhoneState(
                battery=BatteryInfo(**(cached.get("battery") or {})),
                storage=StorageInfo(**(cached.get("storage") or {})),
                network=NetworkInfo(**(cached.get("network") or {})),
                clipboard=cached.get("clipboard", ""),
                volume=VolumeInfo(**(cached.get("volume") or {})),
                flashlight=bool(cached.get("flashlight", False)),
                notifications_enabled=bool(cached.get("notifications_enabled", True)),
                timestamp=cached.get("timestamp", 0.0),
            )
    except Exception:
        logger.exception("Failed to read cached phone state")

    raise HTTPException(status_code=503, detail="No phone connected and no cached state available")


@router.post("/state", response_model=StatusResponse)
async def update_phone_state(state: PhoneState) -> StatusResponse:
    """Update phone state (called by mobile companion app)."""
    logger.info("Phone state updated: battery=%s%%, storage=%s%%",
                state.battery.level, state.storage.used_percent)
    try:
        from dash_backend.cache.simple_cache import get_cache

        get_cache().set(
            "phone_state_latest",
            {
                "battery": state.battery.model_dump(),
                "storage": state.storage.model_dump(),
                "network": state.network.model_dump(),
                "clipboard": state.clipboard,
                "volume": state.volume.model_dump(),
                "flashlight": state.flashlight,
                "notifications_enabled": state.notifications_enabled,
                "timestamp": state.timestamp,
            },
            ttl=3600.0,
        )
    except Exception:
        logger.exception("Failed to store phone state")
    return StatusResponse(status="ok", details={"message": "Phone state updated"})


# ── Battery Endpoint ─────────────────────────────────────────


@router.get("/battery", response_model=StatusResponse)
async def battery_info(serial: Optional[str] = None) -> StatusResponse:
    """Get battery information via ADB."""
    try:
        service = _adb()
        result = await service.get_battery(serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details=result.get("battery", result),
        )
    except Exception as exc:
        logger.exception("battery_info failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Clipboard Endpoints ──────────────────────────────────────


@router.get("/clipboard", response_model=StatusResponse)
async def get_clipboard(serial: Optional[str] = None) -> StatusResponse:
    """Read text from phone clipboard via ADB."""
    try:
        service = _adb()
        result = await service.read_clipboard(serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"text": result.get("text", "")},
        )
    except Exception as exc:
        logger.exception("get_clipboard failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clipboard", response_model=StatusResponse)
async def set_clipboard(req: ClipboardWriteRequest, serial: Optional[str] = None) -> StatusResponse:
    """Write text to phone clipboard via ADB."""
    try:
        service = _adb()
        result = await service.write_clipboard(req.text, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("set_clipboard failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Volume Endpoints ─────────────────────────────────────────


@router.get("/volume", response_model=VolumeInfo)
async def get_volume(serial: Optional[str] = None) -> VolumeInfo:
    """Get current phone volume level (via ADB)."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "media", "volume", "--get", "music"],
        )
        volume = 0
        if result.get("ok"):
            try:
                volume = int(result.get("stdout", "").strip())
            except (TypeError, ValueError):
                volume = 0
        return VolumeInfo(volume=volume)
    except Exception as exc:
        logger.exception("get_volume failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volume", response_model=StatusResponse)
async def set_volume(req: VolumeSetRequest, serial: Optional[str] = None) -> StatusResponse:
    """Set phone volume level (0-100) via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "media", "volume", "--set",
             str(req.level), "music"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": f"Volume set to {req.level}"},
        )
    except Exception as exc:
        logger.exception("set_volume failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volume/mute", response_model=StatusResponse)
async def toggle_mute(serial: Optional[str] = None) -> StatusResponse:
    """Toggle phone mute state via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "media", "volume", "--mute", "music"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": "Mute toggled"},
        )
    except Exception as exc:
        logger.exception("toggle_mute failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Flashlight Endpoints ─────────────────────────────────────


@router.get("/flashlight", response_model=StatusResponse)
async def get_flashlight(serial: Optional[str] = None) -> StatusResponse:
    """Get flashlight state via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "dumpsys", "camera"],
        )
        enabled = "flash" in result.get("stdout", "").lower()
        return StatusResponse(status="ok", details={"enabled": enabled})
    except Exception as exc:
        logger.exception("get_flashlight failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/flashlight", response_model=StatusResponse)
async def toggle_flashlight(req: FlashlightToggleRequest, serial: Optional[str] = None) -> StatusResponse:
    """Toggle flashlight on/off via ADB."""
    try:
        service = _adb()
        # Use camera flash toggle via keyevent (best-effort)
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "input", "keyevent", "KEYCODE_CAMERA"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": f"Flashlight {'on' if req.enabled else 'off'} requested"},
        )
    except Exception as exc:
        logger.exception("toggle_flashlight failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Notification Endpoints ───────────────────────────────────


@router.get("/notifications", response_model=StatusResponse)
async def get_notifications(serial: Optional[str] = None) -> StatusResponse:
    """Get notification list from phone via ADB."""
    try:
        service = _adb()
        result = await service.get_notifications(serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"notifications": result.get("notifications", [])},
        )
    except Exception as exc:
        logger.exception("get_notifications failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/notifications/clear", response_model=StatusResponse)
async def clear_notifications(serial: Optional[str] = None) -> StatusResponse:
    """Clear all notifications on phone via ADB."""
    try:
        service = _adb()
        result = await service.clear_notifications(serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("clear_notifications failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Apps Endpoints ───────────────────────────────────────────


@router.get("/apps", response_model=StatusResponse)
async def get_installed_apps(serial: Optional[str] = None, package_hint: str = "") -> StatusResponse:
    """Get list of installed apps from phone via ADB."""
    try:
        service = _adb()
        result = await service.list_apps(serial, package_hint)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"apps": result.get("packages", [])},
        )
    except Exception as exc:
        logger.exception("get_installed_apps failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/apps/open", response_model=StatusResponse)
async def open_app(req: OpenAppRequest, serial: Optional[str] = None) -> StatusResponse:
    """Open an app on the phone via ADB."""
    try:
        service = _adb()
        result = await service.open_app(req.package, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("open_app failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/apps/close", response_model=StatusResponse)
async def close_app(req: OpenAppRequest, serial: Optional[str] = None) -> StatusResponse:
    """Close/force-stop an app on the phone via ADB."""
    try:
        service = _adb()
        result = await service.close_app(req.package, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("close_app failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Files Endpoints ──────────────────────────────────────────


@router.get("/files/list", response_model=StatusResponse)
async def list_files(path: str = "/sdcard", serial: Optional[str] = None) -> StatusResponse:
    """List files in a directory on the phone via ADB."""
    try:
        service = _adb()
        result = await service.list_files(path, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"path": path, "files": result.get("files", [])},
        )
    except Exception as exc:
        logger.exception("list_files failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/push", response_model=StatusResponse)
async def push_file(req: PushFileRequest, serial: Optional[str] = None) -> StatusResponse:
    """Push a local file to the phone via ADB."""
    try:
        service = _adb()
        result = await service.push_file(req.local_path, req.device_path, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("push_file failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/pull", response_model=StatusResponse)
async def pull_file(device_path: str, local_path: str, serial: Optional[str] = None) -> StatusResponse:
    """Pull a file from the phone to the local machine via ADB."""
    try:
        service = _adb()
        result = await service.pull_file(device_path, local_path, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("pull_file failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── SMS Endpoints (permission-gated) ─────────────────────────


@router.post("/sms/send", response_model=StatusResponse)
async def send_sms(req: SendSmsRequest, serial: Optional[str] = None) -> StatusResponse:
    """Send an SMS via ADB (requires SMS permission/confirmation)."""
    try:
        service = _adb()
        result = await service.send_sms(req.phone_number, req.message, serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": result.get("summary", "")},
        )
    except Exception as exc:
        logger.exception("send_sms failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/sms/list", response_model=StatusResponse)
async def list_sms(serial: Optional[str] = None, limit: int = 20) -> StatusResponse:
    """List recent SMS messages (requires SMS read permission)."""
    try:
        service = _adb()
        result = await service.list_sms(serial, limit)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"messages": result.get("messages", [])},
        )
    except Exception as exc:
        logger.exception("list_sms failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Call Status ──────────────────────────────────────────────


@router.get("/call/status", response_model=StatusResponse)
async def call_status(serial: Optional[str] = None) -> StatusResponse:
    """Get current telephony call status via ADB."""
    try:
        service = _adb()
        result = await service.get_call_status(serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"status": result.get("status", "unknown")},
        )
    except Exception as exc:
        logger.exception("call_status failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Location ─────────────────────────────────────────────────


@router.get("/location", response_model=StatusResponse)
async def get_location(serial: Optional[str] = None) -> StatusResponse:
    """Get device location via ADB (requires location permission)."""
    try:
        service = _adb()
        result = await service.get_location(serial)
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"location": result.get("location")},
        )
    except Exception as exc:
        logger.exception("get_location failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Media Endpoints ───────────────────────────────────────────


@router.get("/media", response_model=StatusResponse)
async def get_media_info(serial: Optional[str] = None) -> StatusResponse:
    """Get current media info from phone via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "dumpsys", "media_session"],
        )
        playing = "state=PLAYING" in result.get("stdout", "")
        artist = title = ""
        for line in result.get("stdout", "").splitlines():
            if "metadata" in line.lower() and "title=" in line:
                title = line.split("title=")[-1].strip()
            if "metadata" in line.lower() and "artist=" in line:
                artist = line.split("artist=")[-1].strip()
        return StatusResponse(status="ok", details={
            "playing": playing, "artist": artist, "title": title,
        })
    except Exception as exc:
        logger.exception("get_media_info failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/media/play", response_model=StatusResponse)
async def media_play(serial: Optional[str] = None) -> StatusResponse:
    """Play media on phone via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "input", "keyevent", "KEYCODE_MEDIA_PLAY"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": "Media play sent"},
        )
    except Exception as exc:
        logger.exception("media_play failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/media/pause", response_model=StatusResponse)
async def media_pause(serial: Optional[str] = None) -> StatusResponse:
    """Pause media on phone via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "input", "keyevent", "KEYCODE_MEDIA_PAUSE"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": "Media pause sent"},
        )
    except Exception as exc:
        logger.exception("media_pause failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/media/next", response_model=StatusResponse)
async def media_next(serial: Optional[str] = None) -> StatusResponse:
    """Skip to next track on phone via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "input", "keyevent", "KEYCODE_MEDIA_NEXT"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": "Media next sent"},
        )
    except Exception as exc:
        logger.exception("media_next failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/media/previous", response_model=StatusResponse)
async def media_previous(serial: Optional[str] = None) -> StatusResponse:
    """Go to previous track on phone via ADB."""
    try:
        service = _adb()
        result = await service._adb(
            [*service._device_prefix(serial), "shell", "input", "keyevent", "KEYCODE_MEDIA_PREVIOUS"],
        )
        return StatusResponse(
            status="ok" if result.get("ok") else "error",
            details={"message": "Media previous sent"},
        )
    except Exception as exc:
        logger.exception("media_previous failed")
        raise HTTPException(status_code=500, detail=str(exc))
