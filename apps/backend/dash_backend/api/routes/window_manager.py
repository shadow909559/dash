"""REST API routes for window management: focus, close, move, resize, snap, list windows.

Provides HTTP endpoints for all window manager operations.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/windows", tags=["windows"])


# ── Request / Response Models ────────────────────────────────


class WindowActionRequest(BaseModel):
    title: str = Field(..., description="Window title or substring to match")


class MoveWindowRequest(BaseModel):
    title: str = Field(..., description="Window title or substring to match")
    x: int = Field(..., description="Target X coordinate")
    y: int = Field(..., description="Target Y coordinate")


class ResizeWindowRequest(BaseModel):
    title: str = Field(..., description="Window title or substring to match")
    width: int = Field(..., description="New width in pixels")
    height: int = Field(..., description="New height in pixels")


class SnapWindowRequest(BaseModel):
    title: str = Field(..., description="Window title or substring to match")
    position: str = Field(
        ...,
        description="Snap position",
        pattern="^(left|right|top-left|top-right|bottom-left|bottom-right|top|bottom|center|maximize)$",
    )


class StatusResponse(BaseModel):
    status: str = "ok"
    details: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────


@router.get("", response_model=StatusResponse)
async def list_windows() -> StatusResponse:
    """List all visible windows."""
    try:
        from dash_backend.services.window import WindowService

        svc = WindowService()
        result = await svc.list_windows()
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("list_windows failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/focus", response_model=StatusResponse)
async def focus_window(req: WindowActionRequest) -> StatusResponse:
    """Bring a window with matching title to front."""
    try:
        from dash_backend.services.window import WindowService

        svc = WindowService()
        result = await svc.focus(req.title)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("focus_window failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/close", response_model=StatusResponse)
async def close_window(req: WindowActionRequest) -> StatusResponse:
    """Close a window with matching title."""
    try:
        from dash_backend.services.window import WindowService

        svc = WindowService()
        result = await svc.close_window(req.title)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("close_window failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/minimize", response_model=StatusResponse)
async def minimize_window(req: WindowActionRequest) -> StatusResponse:
    """Minimize a window with matching title."""
    try:
        from dash_backend.services.window import WindowService

        svc = WindowService()
        result = await svc.minimize(req.title)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("minimize_window failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/maximize", response_model=StatusResponse)
async def maximize_window(req: WindowActionRequest) -> StatusResponse:
    """Maximize a window with matching title."""
    try:
        from dash_backend.services.window import WindowService

        svc = WindowService()
        result = await svc.maximize(req.title)
        return StatusResponse(details=result)
    except Exception as exc:
        logger.exception("maximize_window failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/move", response_model=StatusResponse)
async def move_window(req: MoveWindowRequest) -> StatusResponse:
    """Move a window to specific screen coordinates."""
    try:
        import sys

        if sys.platform != "win32":
            return StatusResponse(status="error", details={"summary": "Windows only"})

        import ctypes

        user32 = ctypes.windll.user32
        from dash_backend.tools.window_management_tools import _find_window

        hwnd = _find_window(req.title)
        if hwnd is None:
            raise HTTPException(status_code=404, detail=f"Window '{req.title}' not found")
        user32.SetWindowPos(hwnd, 0, req.x, req.y, 0, 0, 0x0001 | 0x0004)
        return StatusResponse(details={"summary": f"Moved window to ({req.x}, {req.y})"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resize", response_model=StatusResponse)
async def resize_window(req: ResizeWindowRequest) -> StatusResponse:
    """Resize a window to specific dimensions."""
    try:
        import sys

        if sys.platform != "win32":
            return StatusResponse(status="error", details={"summary": "Windows only"})

        import ctypes

        user32 = ctypes.windll.user32
        from dash_backend.tools.window_management_tools import _find_window

        hwnd = _find_window(req.title)
        if hwnd is None:
            raise HTTPException(status_code=404, detail=f"Window '{req.title}' not found")
        user32.SetWindowPos(hwnd, 0, 0, 0, req.width, req.height, 0x0002 | 0x0004)
        return StatusResponse(details={"summary": f"Resized window to {req.width}x{req.height}"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/snap", response_model=StatusResponse)
async def snap_window(req: SnapWindowRequest) -> StatusResponse:
    """Snap a window to a screen position."""
    try:
        import sys

        if sys.platform != "win32":
            return StatusResponse(status="error", details={"summary": "Windows only"})

        import ctypes

        user32 = ctypes.windll.user32
        from dash_backend.tools.window_management_tools import _find_window

        hwnd = _find_window(req.title)
        if hwnd is None:
            raise HTTPException(status_code=404, detail=f"Window '{req.title}' not found")

        screen_width = user32.GetSystemMetrics(0)
        screen_height = user32.GetSystemMetrics(1)
        half_w = screen_width // 2
        half_h = screen_height // 2

        snap_positions = {
            "left": (0, 0, half_w, screen_height),
            "right": (half_w, 0, half_w, screen_height),
            "top-left": (0, 0, half_w, half_h),
            "top-right": (half_w, 0, half_w, half_h),
            "bottom-left": (0, half_h, half_w, half_h),
            "bottom-right": (half_w, half_h, half_w, half_h),
            "top": (0, 0, screen_width, half_h),
            "bottom": (0, half_h, screen_width, half_h),
            "center": (screen_width // 4, screen_height // 4, screen_width // 2, screen_height // 2),
            "maximize": (0, 0, screen_width, screen_height),
        }

        x, y, w, h = snap_positions.get(req.position, snap_positions["left"])
        user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)
        return StatusResponse(details={"summary": f"Snapped window to {req.position}"})
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/active", response_model=StatusResponse)
async def get_active_window() -> StatusResponse:
    """Detect the currently active (foreground) window."""
    try:
        import sys

        if sys.platform != "win32":
            return StatusResponse(status="error", details={"summary": "Windows only"})

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        return StatusResponse(
            details={
                "hwnd": int(hwnd),
                "title": title or "Unknown",
                "rect": {
                    "left": rect.left,
                    "top": rect.top,
                    "right": rect.right,
                    "bottom": rect.bottom,
                    "width": rect.right - rect.left,
                    "height": rect.bottom - rect.top,
                },
            }
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

