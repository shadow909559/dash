"""Command dispatch for WebSocket commands from Android/desktop clients.

Each command maps to a handler function that receives (command, payload)
and returns a result dict. The dispatch table at the bottom makes it
trivial to add new commands without touching the WebSocket router.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ── Handler functions ──────────────────────────────────────────────────────
# Each takes (command: str, payload: dict) and returns a result dict.
# Imports are deferred to avoid circular imports and keep cold-start fast.


async def _handle_volume(command: str, payload: dict) -> dict:
    from dash_backend.services.media import MediaService
    svc = MediaService()
    if command == "set_volume":
        return await svc.set_volume(payload.get("level", 50))
    elif command == "volume_up":
        return await svc.volume_up(payload.get("amount", 5))
    elif command == "volume_down":
        return await svc.volume_down(payload.get("amount", 5))
    elif command == "set_brightness":
        return await svc.set_brightness(payload.get("level", 50))
    return {}


async def _handle_media(command: str, payload: dict) -> dict:
    from dash_backend.services.media import MediaService
    svc = MediaService()
    action = payload.get("action", "play")
    if action in ("play", "pause"):
        return await svc.media_play_pause()
    elif action == "next":
        return await svc.media_next()
    elif action == "previous":
        return await svc.media_prev()
    elif action == "stop":
        return await svc.media_stop()
    return {"summary": f"Unknown media action: {action}"}


async def _handle_window(command: str, payload: dict) -> dict:
    from dash_backend.services.window import WindowService
    svc = WindowService()
    title = payload.get("title", "")
    if command == "focus_window":
        return await svc.focus(title)
    elif command == "close_window":
        return await svc.close_window(title)
    elif command == "minimize_window":
        return await svc.minimize(title)
    elif command == "maximize_window":
        return await svc.maximize(title)
    return {}


async def _handle_window_move(command: str, payload: dict) -> dict:
    import ctypes
    from dash_backend.tools.window_management_tools import _find_window
    user32 = ctypes.windll.user32
    title = payload.get("title", "")
    hwnd = _find_window(title)
    if hwnd is None:
        raise RuntimeError(f"Window '{title}' not found")

    if command == "move_window":
        x, y = payload.get("x", 0), payload.get("y", 0)
        user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)
        return {"summary": f"Moved window '{title}' to ({x}, {y})"}
    elif command == "resize_window":
        w, h = payload.get("width", 800), payload.get("height", 600)
        user32.SetWindowPos(hwnd, 0, 0, 0, w, h, 0x0002 | 0x0004)
        return {"summary": f"Resized window '{title}' to {w}x{h}"}
    elif command == "snap_window":
        return _snap_window(hwnd, payload.get("position", "left"))
    return {}


def _snap_window(hwnd, position: str) -> dict:
    import ctypes
    user32 = ctypes.windll.user32
    sw = user32.GetSystemMetrics(0)
    sh = user32.GetSystemMetrics(1)
    hw, hh = sw // 2, sh // 2
    snaps = {
        "left": (0, 0, hw, sh), "right": (hw, 0, hw, sh),
        "top-left": (0, 0, hw, hh), "top-right": (hw, 0, hw, hh),
        "bottom-left": (0, hh, hw, hh), "bottom-right": (hw, hh, hw, hh),
        "top": (0, 0, sw, hh), "bottom": (0, hh, sw, hh),
        "center": (sw // 4, sh // 4, sw // 2, sh // 2),
        "maximize": (0, 0, sw, sh),
    }
    x, y, w, h = snaps.get(position, snaps["left"])
    user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)
    return {"summary": f"Snapped window to {position}"}


async def _handle_power(command: str, payload: dict) -> dict:
    from dash_backend.services.power import PowerService
    svc = PowerService()
    actions = {"lock_desktop": svc.lock, "sleep_desktop": svc.sleep,
               "restart_desktop": svc.restart, "shutdown_desktop": svc.shutdown}
    return await actions[command]()


async def _handle_clipboard(command: str, payload: dict) -> dict:
    from dash_backend.services.clipboard import ClipboardService
    svc = ClipboardService()
    if command == "clipboard_read":
        return await svc.read()
    elif command == "clipboard_write":
        return await svc.copy(payload.get("text", ""))
    elif command == "clipboard_clear":
        return await svc.clear()
    return {}


async def _handle_mouse(command: str, payload: dict) -> dict:
    from dash_backend.services.mouse import MouseService
    svc = MouseService()
    if command == "mouse_move":
        return await svc.move(payload.get("x", 0), payload.get("y", 0))
    elif command == "mouse_click":
        return await svc.click(payload.get("button", "left"))
    return {}


async def _handle_keyboard(command: str, payload: dict) -> dict:
    from dash_backend.services.keyboard import KeyboardService
    return await KeyboardService().type_text(payload.get("text", ""))


async def _handle_launch(command: str, payload: dict) -> dict:
    from dash_backend.services.applications import ApplicationService
    return await ApplicationService().launch_by_name(payload.get("app", ""))


async def _handle_file_op(command: str, payload: dict) -> dict:
    from pathlib import Path
    import shutil
    from dash_backend.security.path_guard import PathDenied, ensure_writable

    if command == "copy_file":
        src = ensure_writable(payload["source"])
        dst = ensure_writable(payload["destination"])
        if not src.exists():
            raise RuntimeError(f"Source not found: {payload['source']}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        def _copy():
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        await asyncio.to_thread(_copy)
        return {"summary": f"Copied {payload['source']} -> {payload['destination']}"}

    elif command == "move_file":
        src = ensure_writable(payload["source"])
        dst = ensure_writable(payload["destination"])
        if not src.exists():
            raise RuntimeError(f"Source not found: {payload['source']}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.move, str(src), str(dst))
        return {"summary": f"Moved {payload['source']} -> {payload['destination']}"}

    elif command == "rename_file":
        p = ensure_writable(payload["path"])
        if not p.exists():
            raise RuntimeError(f"Not found: {payload['path']}")
        new_path = p.parent / payload["new_name"]
        ensure_writable(str(new_path))
        await asyncio.to_thread(p.rename, new_path)
        return {"summary": f"Renamed to {payload['new_name']}"}

    elif command == "delete_file":
        p = ensure_writable(payload["path"])
        if not p.exists():
            raise RuntimeError(f"Not found: {payload['path']}")
        permanent = payload.get("permanent", False)

        def _delete():
            if permanent or os.name != "nt":
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return f"Deleted {p.name}"
            import ctypes
            buf = ctypes.create_unicode_buffer(str(p) + "\0\0")
            ctypes.windll.shell32.SHFileOperationW(
                ctypes.byref(ctypes.c_int(0)),
                ctypes.byref(ctypes.c_int(3)),  # FO_DELETE
                buf, None, ctypes.byref(ctypes.c_int(0x40)),  # FOF_ALLOWUNDO
                0,
            )
            return f"Moved {p.name} to Recycle Bin"

        return {"summary": await asyncio.to_thread(_delete)}
    return {}


async def _handle_screenshot(command: str, payload: dict) -> dict:
    import base64, io
    def _take():
        import pyautogui
        buf = io.BytesIO()
        pyautogui.screenshot().save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    img_b64 = await asyncio.to_thread(_take)
    return {"screenshot_base64": img_b64, "summary": "Screenshot captured"}


async def _handle_system_status(command: str, payload: dict) -> dict:
    from dash_backend.services.system.system_info import get_system_info
    return get_system_info()


# ── Dispatch table ─────────────────────────────────────────────────────────
# Maps command name -> handler function. Add new commands here.

COMMAND_HANDLERS: dict[str, Any] = {
    # Volume & brightness
    "set_volume": _handle_volume,
    "volume_up": _handle_volume,
    "volume_down": _handle_volume,
    "set_brightness": _handle_volume,
    # Media
    "media_control": _handle_media,
    # Window management
    "focus_window": _handle_window,
    "close_window": _handle_window,
    "minimize_window": _handle_window,
    "maximize_window": _handle_window,
    "move_window": _handle_window_move,
    "resize_window": _handle_window_move,
    "snap_window": _handle_window_move,
    # Power
    "lock_desktop": _handle_power,
    "sleep_desktop": _handle_power,
    "restart_desktop": _handle_power,
    "shutdown_desktop": _handle_power,
    # Clipboard
    "clipboard_read": _handle_clipboard,
    "clipboard_write": _handle_clipboard,
    "clipboard_clear": _handle_clipboard,
    # Input
    "mouse_move": _handle_mouse,
    "mouse_click": _handle_mouse,
    "keyboard_type": _handle_keyboard,
    # Applications
    "launch_app": _handle_launch,
    # Files
    "copy_file": _handle_file_op,
    "move_file": _handle_file_op,
    "rename_file": _handle_file_op,
    "delete_file": _handle_file_op,
    # Capture
    "take_screenshot": _handle_screenshot,
    # System
    "get_system_status": _handle_system_status,
}


async def execute_command(command: str, payload: dict) -> dict:
    """Execute a command by name and return the result dict.

    Returns the handler's result on success. Raises on unknown command
    or handler failure — the caller wraps in try/except.
    """
    handler = COMMAND_HANDLERS.get(command)
    if handler is None:
        raise ValueError(f"Unknown command: {command}")
    return await handler(command, payload)
