"""REST API routes for desktop control: volume, brightness, clipboard, mouse, keyboard, power, screenshot.

Provides HTTP endpoints for all remote control operations that can be called
from the desktop UI or mobile app.
"""

from __future__ import annotations

from typing import Any, Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.logging_config import get_logger
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.services.audit_logs import get_audit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/desktop", tags=["desktop"])


# ── Request / Response Models ────────────────────────────────


class VolumeResponse(BaseModel):
    volume: float = 0.0
    muted: bool = False
    summary: str = ""


class VolumeSetRequest(BaseModel):
    level: int = Field(..., ge=0, le=100, description="Volume level 0-100")


class MuteRequest(BaseModel):
    muted: bool = True


class BrightnessResponse(BaseModel):
    brightness: int = 0
    summary: str = ""


class BrightnessSetRequest(BaseModel):
    level: int = Field(..., ge=0, le=100, description="Brightness level 0-100")


class ClipboardResponse(BaseModel):
    text: str = ""
    summary: str = ""


class ClipboardWriteRequest(BaseModel):
    text: str = Field(..., description="Text to copy to clipboard")


class MouseMoveRequest(BaseModel):
    x: int
    y: int


class MouseClickRequest(BaseModel):
    button: str = "left"
    x: int | None = None
    y: int | None = None


class KeyPressRequest(BaseModel):
    key: str


class KeyTextRequest(BaseModel):
    text: str


class PowerResponse(BaseModel):
    summary: str = ""


class PowerRequest(BaseModel):
    force: bool = False
    timeout: int = 30


class StatusResponse(BaseModel):
    status: str = "ok"
    details: dict[str, Any] = Field(default_factory=dict)


# ── Volume Endpoints ─────────────────────────────────────────


@router.get("/volume", response_model=VolumeResponse)
async def get_volume() -> VolumeResponse:
    """Get current system volume level."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.get_volume()
        return VolumeResponse(
            volume=result.get("volume", 0),
            muted=result.get("muted", False),
            summary=result.get("summary", ""),
        )
    except Exception as exc:
        logger.exception("get_volume failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volume", response_model=VolumeResponse)
async def set_volume(req: VolumeSetRequest) -> VolumeResponse:
    """Set system volume level (0-100)."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.set_volume(req.level)
        return VolumeResponse(volume=float(req.level), summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("set_volume failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volume/mute", response_model=VolumeResponse)
async def set_mute(req: MuteRequest) -> VolumeResponse:
    """Mute or unmute system audio."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.set_mute(muted=req.muted)
        return VolumeResponse(summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("set_mute failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volume/up", response_model=PowerResponse)
async def volume_up(amount: int = 5) -> PowerResponse:
    """Increase volume by amount steps."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.volume_up(amount=amount)
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("volume_up failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/volume/down", response_model=PowerResponse)
async def volume_down(amount: int = 5) -> PowerResponse:
    """Decrease volume by amount steps."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.volume_down(amount=amount)
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("volume_down failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Brightness Endpoints ─────────────────────────────────────


@router.get("/brightness", response_model=BrightnessResponse)
async def get_brightness() -> BrightnessResponse:
    """Get current screen brightness level."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.get_brightness()
        return BrightnessResponse(
            brightness=result.get("brightness", 0),
            summary=result.get("summary", ""),
        )
    except Exception as exc:
        logger.exception("get_brightness failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/brightness", response_model=BrightnessResponse)
async def set_brightness(req: BrightnessSetRequest) -> BrightnessResponse:
    """Set screen brightness level (0-100)."""
    try:
        from dash_backend.services.media import MediaService

        svc = MediaService()
        result = await svc.set_brightness(req.level)
        return BrightnessResponse(brightness=req.level, summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("set_brightness failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Clipboard Endpoints ──────────────────────────────────────


@router.get("/clipboard", response_model=ClipboardResponse)
async def clipboard_read() -> ClipboardResponse:
    """Read text from system clipboard."""
    try:
        from dash_backend.services.clipboard import ClipboardService

        svc = ClipboardService()
        result = await svc.read()
        return ClipboardResponse(text=result.get("text", ""), summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("clipboard_read failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/clipboard", response_model=ClipboardResponse)
async def clipboard_write(req: ClipboardWriteRequest) -> ClipboardResponse:
    """Write text to system clipboard."""
    try:
        from dash_backend.services.clipboard import ClipboardService

        svc = ClipboardService()
        result = await svc.copy(req.text)
        return ClipboardResponse(text=req.text, summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("clipboard_write failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/clipboard", response_model=PowerResponse)
async def clipboard_clear() -> PowerResponse:
    """Clear the system clipboard."""
    try:
        from dash_backend.services.clipboard import ClipboardService

        svc = ClipboardService()
        result = await svc.clear()
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("clipboard_clear failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Mouse Endpoints ──────────────────────────────────────────


@router.post("/mouse/move", response_model=StatusResponse)
async def mouse_move(req: MouseMoveRequest) -> StatusResponse:
    """Move mouse cursor to absolute coordinates."""
    try:
        from dash_backend.services.mouse import MouseService

        svc = MouseService()
        result = await svc.move(req.x, req.y)
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/mouse/click", response_model=StatusResponse)
async def mouse_click(req: MouseClickRequest) -> StatusResponse:
    """Click mouse button at current or specified position."""
    try:
        from dash_backend.services.mouse import MouseService

        svc = MouseService()
        if req.x is not None and req.y is not None:
            await svc.move(req.x, req.y)
        result = await svc.click(button=req.button)
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/mouse/double-click", response_model=StatusResponse)
async def mouse_double_click() -> StatusResponse:
    """Double-click at current mouse position."""
    try:
        from dash_backend.services.mouse import MouseService

        svc = MouseService()
        result = await svc.double_click()
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/mouse/scroll", response_model=StatusResponse)
async def mouse_scroll(clicks: int = 1) -> StatusResponse:
    """Scroll the mouse wheel."""
    try:
        from dash_backend.services.mouse import MouseService

        svc = MouseService()
        result = await svc.scroll(clicks=clicks)
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/mouse/position", response_model=StatusResponse)
async def mouse_position() -> StatusResponse:
    """Get current mouse cursor position."""
    try:
        from dash_backend.services.mouse import MouseService

        svc = MouseService()
        result = await svc.get_position()
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Keyboard Endpoints ────────────────────────────────────────


@router.post("/keyboard/type", response_model=StatusResponse)
async def keyboard_type(req: KeyTextRequest) -> StatusResponse:
    """Type text at current cursor position."""
    try:
        from dash_backend.services.keyboard import KeyboardService

        svc = KeyboardService()
        result = await svc.type_text(req.text)
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/keyboard/press", response_model=StatusResponse)
async def keyboard_press(req: KeyPressRequest) -> StatusResponse:
    """Press and release a single key."""
    try:
        from dash_backend.services.keyboard import KeyboardService

        svc = KeyboardService()
        result = await svc.press(req.key)
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/keyboard/hotkey", response_model=StatusResponse)
async def keyboard_hotkey(keys: list[str]) -> StatusResponse:
    """Press a keyboard shortcut (e.g., ['ctrl', 'c'])."""
    try:
        from dash_backend.services.keyboard import KeyboardService

        svc = KeyboardService()
        result = await svc.hotkey(*keys)
        return StatusResponse(details=result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Power Endpoints (DANGEROUS — require auth + audit log) ──────


@router.post("/power/shutdown", response_model=PowerResponse)
async def power_shutdown(
    req: PowerRequest = PowerRequest(),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> PowerResponse:
    """Shutdown the computer. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.shutdown(force=req.force, timeout=req.timeout)
        # Audit log
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="shutdown", category="remote_control", status="success",
                details={"force": req.force, "timeout": req.timeout},
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        logger.exception("power_shutdown failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/power/restart", response_model=PowerResponse)
async def power_restart(
    req: PowerRequest = PowerRequest(),
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Restart the computer. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.restart(force=req.force, timeout=req.timeout)
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="restart", category="remote_control", status="success",
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/power/lock", response_model=PowerResponse)
async def power_lock(
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Lock the workstation. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.lock()
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="lock", category="remote_control", status="success",
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/power/sleep", response_model=PowerResponse)
async def power_sleep(
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Put the system to sleep. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.sleep()
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="sleep", category="remote_control", status="success",
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/power/hibernate", response_model=PowerResponse)
async def power_hibernate(
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Hibernate the system. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.hibernate()
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="hibernate", category="remote_control", status="success",
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/power/logoff", response_model=PowerResponse)
async def power_logoff(
    force: bool = False,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Log off the current user. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.logoff(force=force)
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="logoff", category="remote_control", status="success",
                details={"force": force},
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/power/abort-shutdown", response_model=PowerResponse)
async def power_abort_shutdown(
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Abort a pending shutdown. Requires authentication."""
    try:
        from dash_backend.services.power import PowerService

        svc = PowerService()
        result = await svc.abort_shutdown()
        try:
            get_audit_service().log(
                event_type="power", user_id=str(current_user.id or ""),
                action="abort_shutdown", category="remote_control", status="success",
            )
        except Exception:
            pass
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Screenshot Endpoint ────────────────────────────────────────


@router.post("/screenshot", response_model=StatusResponse)
async def take_screenshot() -> StatusResponse:
    """Capture a screenshot and return as base64 PNG."""
    try:
        import pyautogui
        import io
        import base64

        screenshot = pyautogui.screenshot()
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return StatusResponse(details={"image_base64": b64, "size": len(buf.getvalue())})
    except ImportError:
        try:
            from PIL import ImageGrab
            import io
            import base64

            screenshot = ImageGrab.grab()
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return StatusResponse(details={"image_base64": b64, "size": len(buf.getvalue())})
        except ImportError:
            raise HTTPException(status_code=500, detail="Screenshot requires pyautogui or PIL")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Notification Endpoint ───────────────────────────────────────


class NotificationRequest(BaseModel):
    title: str = "DASH"
    message: str = ""
    duration: int = 5


@router.post("/notification", response_model=PowerResponse)
async def show_notification(req: NotificationRequest) -> PowerResponse:
    """Show a desktop notification."""
    try:
        from dash_backend.services.notifications import NotificationService

        svc = NotificationService()
        result = await svc.show(title=req.title, message=req.message, duration=req.duration)
        return PowerResponse(summary=result.get("summary", ""))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

