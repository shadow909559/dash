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

router = APIRouter(prefix="/desktop", tags=["desktop"], dependencies=[Depends(get_current_user)])


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
    # Two-phase approval: omit on the first call to request approval, then
    # repeat the call with this id (after approving) to actually execute.
    approval_id: str | None = None


# Approval ids that have been approved and are ready for one-time consumption.
_approved_power_ids: set[str] = set()


def _gate_power_action(operation: str, description: str, approval_id: str | None, force: bool = False) -> None:
    """Two-phase approval gate for CRITICAL power operations.

    When force=True, auto-approves (for trusted mobile companion requests).
    Otherwise uses the normal two-phase approval flow.
    """
    from dash_backend.services.permission_manager import get_permission_manager

    pm = get_permission_manager()
    if approval_id:
        if approval_id in _approved_power_ids:
            _approved_power_ids.discard(approval_id)
            return
        raise HTTPException(status_code=400, detail="Invalid, unapproved, or expired approval_id.")
    if force:
        return  # auto-approve for trusted device requests
    request = pm.request_permission(operation, description)
    if getattr(request, "approved", False):
        return
    raise HTTPException(
        status_code=202,
        detail={
            "approval_required": True,
            "approval_id": request.request_id,
            "operation": operation,
            "level": "critical",
            "description": description,
        },
    )


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


# ── Approval Endpoints (two-phase gate for CRITICAL actions) ──


@router.get("/approvals")
async def list_approvals(
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> StatusResponse:
    """List pending approval requests."""
    from dash_backend.services.permission_manager import get_permission_manager

    pending = [
        {
            "approval_id": r.request_id,
            "operation": r.operation,
            "level": r.level.value,
            "description": r.description,
        }
        for r in get_permission_manager().get_pending_requests()
    ]
    return StatusResponse(status="ok", details={"pending": pending})


@router.post("/approvals/{approval_id}/approve")
async def approve_action(
    approval_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> StatusResponse:
    """Approve a pending action; the id becomes single-use execute permission."""
    from dash_backend.services.permission_manager import get_permission_manager

    if not get_permission_manager().approve_request(approval_id):
        raise HTTPException(status_code=404, detail="Unknown or already-resolved approval id.")
    _approved_power_ids.add(approval_id)
    try:
        get_audit_service().log(
            event_type="approval", user_id=str(getattr(current_user, "id", "")),
            action=f"approve:{approval_id}", category="security", status="success",
        )
    except Exception:
        pass
    return StatusResponse(status="ok", details={"approved": approval_id})


@router.post("/approvals/{approval_id}/deny")
async def deny_action(
    approval_id: str,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> StatusResponse:
    """Deny a pending action. A denied request can never execute."""
    from dash_backend.services.permission_manager import get_permission_manager

    if not get_permission_manager().deny_request(approval_id):
        raise HTTPException(status_code=404, detail="Unknown or already-resolved approval id.")
    try:
        get_audit_service().log(
            event_type="approval", user_id=str(getattr(current_user, "id", "")),
            action=f"deny:{approval_id}", category="security", status="success",
        )
    except Exception:
        pass
    return StatusResponse(status="ok", details={"denied": approval_id})


@router.post("/power/shutdown", response_model=PowerResponse)
async def power_shutdown(
    req: PowerRequest = PowerRequest(),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    session: Annotated[AsyncSession, Depends(get_db_session)] = None,
) -> PowerResponse:
    """Shutdown the computer. Requires authentication AND explicit approval."""
    _gate_power_action("shutdown", f"Shut down this PC (force={req.force}, timeout={req.timeout}s).", req.approval_id, force=req.force)
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
    """Restart the computer. Requires authentication AND explicit approval."""
    _gate_power_action("restart", f"Restart this PC (force={req.force}, timeout={req.timeout}s).", req.approval_id, force=req.force)
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
    req: PowerRequest = PowerRequest(),
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Put the system to sleep. force=True skips approval for trusted devices."""
    _gate_power_action("sleep", "Put this PC to sleep.", req.approval_id, force=req.force)
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
    req: PowerRequest = PowerRequest(),
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> PowerResponse:
    """Hibernate the system. force=True skips approval for trusted devices."""
    _gate_power_action("hibernate", "Hibernate this PC.", req.approval_id, force=req.force)
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
    approval_id: str | None = None,
) -> PowerResponse:
    """Log off the current user. Requires authentication AND explicit approval."""
    _gate_power_action("logoff", f"Log off this Windows session (force={force}).", approval_id)
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


# ── Application Endpoints ────────────────────────────────────


class AppLaunchRequest(BaseModel):
    name: str = Field(..., description="Application name to launch")


class AppCloseRequest(BaseModel):
    name: str = Field(..., description="Application name to close")


@router.get("/applications/search", response_model=list[dict[str, Any]])
async def search_applications(query: str) -> list[dict[str, Any]]:
    """Search for installed applications."""
    try:
        from dash_backend.services.applications import ApplicationService

        svc = ApplicationService()
        return await svc.search_applications(query)
    except Exception as exc:
        logger.exception("search_applications failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/applications/launch", response_model=StatusResponse)
async def launch_application(req: AppLaunchRequest) -> StatusResponse:
    """Launch an application by name."""
    try:
        from dash_backend.services.applications import ApplicationService

        svc = ApplicationService()
        result = await svc.launch_by_name(req.name)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("launch_application failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/applications/close", response_model=StatusResponse)
async def close_application(req: AppCloseRequest) -> StatusResponse:
    """Close an application by name."""
    try:
        from dash_backend.services.applications import ApplicationService

        svc = ApplicationService()
        result = await svc.close(req.name)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("close_application failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/applications/processes", response_model=list[dict[str, Any]])
async def list_processes() -> list[dict[str, Any]]:
    """List running processes."""
    try:
        from dash_backend.services.applications import ApplicationService

        svc = ApplicationService()
        return await svc.list_processes()
    except Exception as exc:
        logger.exception("list_processes failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── File System Endpoints ────────────────────────────────────


class FileRequest(BaseModel):
    path: str


class FileRenameRequest(BaseModel):
    path: str
    new_name: str


class FileMoveRequest(BaseModel):
    source: str
    destination: str


class FileZipRequest(BaseModel):
    source_paths: list[str]
    zip_path: str


class FileUnzipRequest(BaseModel):
    zip_path: str
    extract_to: str


@router.post("/files/read-folder", response_model=dict[str, Any])
async def read_folder(req: FileRequest) -> dict[str, Any]:
    """Read the contents of a folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        return await svc.read_folder(req.path)
    except Exception as exc:
        logger.exception("read_folder failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/create-folder", response_model=StatusResponse)
async def create_folder(req: FileRequest) -> StatusResponse:
    """Create a new folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.create_folder(req.path)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("create_folder failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/delete", response_model=StatusResponse)
async def delete_file_or_folder(req: FileRequest) -> StatusResponse:
    """Delete a file or folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.delete(req.path)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("delete_file_or_folder failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/rename", response_model=StatusResponse)
async def rename_file_or_folder(req: FileRenameRequest) -> StatusResponse:
    """Rename a file or folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.rename(req.path, req.new_name)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("rename_file_or_folder failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/move", response_model=StatusResponse)
async def move_file_or_folder(req: FileMoveRequest) -> StatusResponse:
    """Move a file or folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.move(req.source, req.destination)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("move_file_or_folder failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/copy", response_model=StatusResponse)
async def copy_file_or_folder(req: FileMoveRequest) -> StatusResponse:
    """Copy a file or folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.copy(req.source, req.destination)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("copy_file_or_folder failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/zip", response_model=StatusResponse)
async def zip_files(req: FileZipRequest) -> StatusResponse:
    """Zip files and folders."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.zip(req.source_paths, req.zip_path)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("zip_files failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/unzip", response_model=StatusResponse)
async def unzip_files(req: FileUnzipRequest) -> StatusResponse:
    """Unzip a file."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        result = await svc.unzip(req.zip_path, req.extract_to)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("unzip_files failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/files/metadata", response_model=dict[str, Any])
async def get_metadata(req: FileRequest) -> dict[str, Any]:
    """Get metadata for a file or folder."""
    try:
        from dash_backend.services.files import FileService

        svc = FileService()
        return await svc.get_metadata(req.path)
    except Exception as exc:
        logger.exception("get_metadata failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── Downloads Manager Endpoints ──────────────────────────────


class OrganizeDownloadsRequest(BaseModel):
    dry_run: bool = False


@router.get("/downloads", response_model=dict[str, Any])
async def list_downloads(limit: int = 50) -> dict[str, Any]:
    """List recent downloads."""
    try:
        from dash_backend.services.download_manager import get_download_manager

        manager = get_download_manager()
        return manager.list_downloads(limit=limit)
    except Exception as exc:
        logger.exception("list_downloads failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/downloads/organize", response_model=dict[str, Any])
async def organize_downloads(req: OrganizeDownloadsRequest) -> dict[str, Any]:
    """Organize the downloads folder."""
    try:
        from dash_backend.services.download_manager import get_download_manager

        manager = get_download_manager()
        return manager.auto_organize(dry_run=req.dry_run)
    except Exception as exc:
        logger.exception("organize_downloads failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/downloads/stats", response_model=dict[str, Any])
async def get_download_stats() -> dict[str, Any]:
    """Get statistics for the downloads folder."""
    try:
        from dash_backend.services.download_manager import get_download_manager

        manager = get_download_manager()
        return manager.get_stats()
    except Exception as exc:
        logger.exception("get_download_stats failed")
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