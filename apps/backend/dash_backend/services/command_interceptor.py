"""Command interceptor — detects desktop-control commands from natural language.

When a user sends a message like "open Chrome" or "close Notepad" or "type hello world",
this module intercepts it, executes the action, and returns a result message so the LLM
doesn't need to handle it.
"""

from __future__ import annotations

import re
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ── Patterns ──────────────────────────────────────────────────

_OPEN_PATTERNS = [
    re.compile(r"^(?:open|launch|start|run)\s+(?:the\s+)?(?P<app>.+)$", re.I),
    re.compile(r"^(?:can\s+you|please|hey\s+dash)?\s*(?:open|launch|start|run)\s+(?:the\s+)?(?P<app>.+)$", re.I),
]

_CLOSE_PATTERNS = [
    re.compile(r"^(?:close|kill|stop|shut\s*down|exit)\s+(?:the\s+)?(?P<app>.+)$", re.I),
    re.compile(r"^(?:can\s+you|please|hey\s+dash)?\s*(?:close|kill|stop|shut\s*down|exit)\s+(?:the\s+)?(?P<app>.+)$", re.I),
]

_TYPE_PATTERNS = [
    re.compile(r"^(?:type|write|enter|input)\s+[\"']?(?P<text>.+?)[\"']?$", re.I),
    re.compile(r"^(?:can\s+you|please|hey\s+dash)?\s*(?:type|write|enter|input)\s+[\"']?(?P<text>.+?)[\"']?$", re.I),
]

_KEY_PATTERNS = [
    re.compile(r"^(?:press|hit)\s+(?:the\s+)?(?P<key>enter|tab|escape|backspace|delete|space|up|down|left|right|home|end|page\s*up|page\s*down)$", re.I),
    re.compile(r"^(?:press|hit)\s+(?:the\s+)?ctrl\s*\+\s*(?P<key>[a-z])$", re.I),
    re.compile(r"^(?:press|hit)\s+(?:the\s+)?alt\s*\+\s*(?P<key>[a-z]+)$", re.I),
    re.compile(r"^(?:press|hit)\s+(?:the\s+)?win\s*\+\s*(?P<key>[a-z])$", re.I),
]

_VOLUME_PATTERNS = [
    re.compile(r"^(?:set|turn)\s+volume\s+(?:to\s+)?(?P<level>\d+)(?:\s*%)?$", re.I),
    re.compile(r"^(?:volume|sound)\s+(?:up|louder|increase)$", re.I),
    re.compile(r"^(?:volume|sound)\s+(?:down|quieter|decrease|lower)$", re.I),
    re.compile(r"^(?:mute|unmute)(?:\s+(?:the\s+)?(?:audio|sound|volume))?$", re.I),
]

_POWER_PATTERNS = [
    re.compile(r"^(?:shutdown|shut\s*down|power\s*off)\s+(?:the\s+)?(?:pc|computer|laptop|machine)$", re.I),
    re.compile(r"^(?:restart|reboot)\s+(?:the\s+)?(?:pc|computer|laptop|machine)$", re.I),
    re.compile(r"^(?:sleep|hibernate)\s+(?:the\s+)?(?:pc|computer|laptop|machine)$", re.I),
    re.compile(r"^(?:lock)\s+(?:the\s+)?(?:pc|computer|laptop|machine|screen|windows)$", re.I),
]

_SCREENSHOT_PATTERNS = [
    re.compile(r"^(?:take|capture|grab)\s+(?:a\s+)?(?:screenshot|screen\s*shot)$", re.I),
]

_CLIPBOARD_READ_PATTERNS = [
    re.compile(r"^(?:what(?:'s| is|'s on)\s+(?:the\s+)?(?:clipboard|copied)|read\s+(?:the\s+)?clipboard|paste\s+from\s+clipboard)$", re.I),
]

_CLIPBOARD_WRITE_PATTERNS = [
    re.compile(r"^(?:copy|set)\s+(?:the\s+)?(?:clipboard\s+(?:to|with)\s+)?[\"']?(?P<text>.+?)[\"']?\s*(?:to\s+(?:the\s+)?clipboard)?$", re.I),
]


# ── Interceptor ────────────────────────────────────────────────

async def try_intercept(message: str) -> dict[str, Any] | None:
    """Try to intercept a desktop control command from a chat message.

    Returns None if the message doesn't match any command pattern.
    Returns a dict with 'summary', 'action', and 'details' if a command was executed.
    """
    text = message.strip()

    # ── Open / Launch application ──
    for pat in _OPEN_PATTERNS:
        m = pat.match(text)
        if m:
            app_name = m.group("app").strip().rstrip(".")
            return await _execute_open(app_name)

    # ── Close / Kill application ──
    for pat in _CLOSE_PATTERNS:
        m = pat.match(text)
        if m:
            app_name = m.group("app").strip().rstrip(".")
            return await _execute_close(app_name)

    # ── Type text ──
    for pat in _TYPE_PATTERNS:
        m = pat.match(text)
        if m:
            typed_text = m.group("text").strip()
            return await _execute_type(typed_text)

    # ── Key press ──
    for pat in _KEY_PATTERNS:
        m = pat.match(text)
        if m:
            key = m.group("key").strip().lower().replace(" ", "")
            return await _execute_key(key)

    # ── Volume ──
    for pat in _VOLUME_PATTERNS:
        m = pat.match(text)
        if m:
            matched = m.group(0).lower()
            if "up" in matched or "louder" in matched or "increase" in matched:
                return await _execute_volume_action("up")
            elif "down" in matched or "quieter" in matched or "decrease" in matched or "lower" in matched:
                return await _execute_volume_action("down")
            elif "mute" in matched and "unmute" not in matched:
                return await _execute_volume_action("mute")
            elif "unmute" in matched:
                return await _execute_volume_action("unmute")
            else:
                level = int(m.group("level"))
                return await _execute_volume_set(level)

    # ── Power ──
    for pat in _POWER_PATTERNS:
        m = pat.match(text)
        if m:
            matched = m.group(0).lower()
            if "shutdown" in matched or "power off" in matched:
                return await _execute_power("shutdown")
            elif "restart" in matched or "reboot" in matched:
                return await _execute_power("restart")
            elif "sleep" in matched or "hibernate" in matched:
                return await _execute_power("sleep")
            elif "lock" in matched:
                return await _execute_power("lock")

    # ── Screenshot ──
    for pat in _SCREENSHOT_PATTERNS:
        m = pat.match(text)
        if m:
            return await _execute_screenshot()

    # ── Clipboard read ──
    for pat in _CLIPBOARD_READ_PATTERNS:
        m = pat.match(text)
        if m:
            return await _execute_clipboard_read()

    # ── Clipboard write ──
    for pat in _CLIPBOARD_WRITE_PATTERNS:
        m = pat.match(text)
        if m:
            text_to_copy = m.group("text").strip()
            return await _execute_clipboard_write(text_to_copy)

    return None  # Not a command — pass to LLM


# ── Execution helpers ──────────────────────────────────────────

# Common Windows executables that aren't in the Start Menu registry
_COMMON_EXES: dict[str, str] = {
    "notepad": "notepad.exe",
    "notepad++": "notepad++.exe",
    "calc": "calc.exe",
    "calculator": "calc.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "terminal": "wt.exe",
    "paint": "mspaint.exe",
    "snipping tool": "snippingtool.exe",
    "task manager": "taskmgr.exe",
    "regedit": "regedit.exe",
    "registry": "regedit.exe",
    "control panel": "control.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "word": "winword.exe",
    "wordpad": "write.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "outlook": "outlook.exe",
    "edge": "msedge.exe",
    "edge browser": "msedge.exe",
    "firefox": "firefox.exe",
    "zoom": "zoom.exe",
    "teams": "ms-teams.exe",
    "spotify": "spotify.exe",
    "vscode": "code.exe",
    "visual studio code": "code.exe",
    "code": "code.exe",
    "powershell": "powershell.exe",
    "powershell ise": "powershell_ise.exe",
    "windows terminal": "wt.exe",
    "7zip": "7zfm.exe",
    "7-zip": "7zfm.exe",
}


async def _execute_open(app_name: str) -> dict[str, Any]:
    try:
        from dash_backend.services.applications import ApplicationService
        svc = ApplicationService()

        # First try the normal application search
        try:
            result = await svc.launch_by_name(app_name)
            return {
                "action": "open",
                "app": app_name,
                "summary": result.get("summary", f"Opened {app_name}"),
                "status": result.get("status", "launched"),
            }
        except RuntimeError:
            pass  # Not found in registry — try common executables

        # Try common executables
        exe = _COMMON_EXES.get(app_name.lower())
        if exe:
            import subprocess, os
            try:
                if os.path.exists(exe) or os.sep in exe:

                    subprocess.Popen([exe], shell=True)
                else:
                    # Use 'start' via shell to find it in PATH
                    subprocess.Popen(f"start {exe}", shell=True)
                return {
                    "action": "open",
                    "app": app_name,
                    "summary": f"Opened {app_name} ({exe})",
                    "status": "launched",
                }
            except Exception as inner_exc:
                logger.exception("Failed to start exe %s", exe)
                return {"action": "open", "app": app_name, "error": str(inner_exc),
                        "summary": f"Failed to open {app_name}: {inner_exc}"}

        return {"action": "open", "app": app_name, "error": "Not found",
                "summary": f"Application '{app_name}' not found. Try the full name or exact executable."}
    except Exception as exc:
        logger.exception("Failed to open %s", app_name)
        return {"action": "open", "app": app_name, "error": str(exc),
                "summary": f"Failed to open {app_name}: {exc}"}


async def _execute_close(app_name: str) -> dict[str, Any]:
    try:
        from dash_backend.services.applications import ApplicationService
        svc = ApplicationService()
        result = await svc.close(app_name)
        return {
            "action": "close",
            "app": app_name,
            "summary": result.get("summary", f"Closed {app_name}"),
            "status": result.get("status", "closed"),
        }
    except Exception as exc:
        logger.exception("Failed to close %s", app_name)
        return {"action": "close", "app": app_name, "error": str(exc),
                "summary": f"Failed to close {app_name}: {exc}"}


async def _execute_type(text: str) -> dict[str, Any]:
    try:
        from dash_backend.services.keyboard import KeyboardService
        svc = KeyboardService()
        result = await svc.type_text(text)
        return {"action": "type", "text": text, "summary": f"Typed: {text}",
                "details": result}
    except Exception as exc:
        logger.exception("Failed to type text")
        return {"action": "type", "text": text, "error": str(exc),
                "summary": f"Failed to type: {exc}"}


async def _execute_key(key: str) -> dict[str, Any]:
    try:
        from dash_backend.services.keyboard import KeyboardService
        svc = KeyboardService()
        result = await svc.press(key)
        return {"action": "key", "key": key, "summary": f"Pressed {key}",
                "details": result}
    except Exception as exc:
        logger.exception("Failed to press key %s", key)
        return {"action": "key", "key": key, "error": str(exc),
                "summary": f"Failed to press {key}: {exc}"}


async def _execute_volume_set(level: int) -> dict[str, Any]:
    try:
        from dash_backend.services.media import MediaService
        svc = MediaService()
        result = await svc.set_volume(level)
        return {"action": "volume", "level": level,
                "summary": f"Volume set to {level}%", "details": result}
    except Exception as exc:
        logger.exception("Failed to set volume")
        return {"action": "volume", "level": level, "error": str(exc),
                "summary": f"Failed to set volume: {exc}"}


async def _execute_volume_action(action: str) -> dict[str, Any]:
    try:
        from dash_backend.services.media import MediaService
        svc = MediaService()
        if action == "up":
            result = await svc.volume_up(amount=10)
        elif action == "down":
            result = await svc.volume_down(amount=10)
        elif action == "mute":
            result = await svc.set_mute(muted=True)
        else:
            result = await svc.set_mute(muted=False)
        return {"action": "volume_" + action,
                "summary": result.get("summary", f"Volume {action}"),
                "details": result}
    except Exception as exc:
        logger.exception("Failed volume action %s", action)
        return {"action": "volume_" + action, "error": str(exc),
                "summary": f"Volume {action} failed: {exc}"}


async def _execute_power(action: str) -> dict[str, Any]:
    try:
        from dash_backend.services.power import PowerService
        svc = PowerService()
        if action == "shutdown":
            result = await svc.shutdown(force=True)
        elif action == "restart":
            result = await svc.restart(force=True)
        elif action == "sleep":
            result = await svc.sleep()
        elif action == "lock":
            result = await svc.lock()
        else:
            return {"action": "power", "error": "Unknown action",
                    "summary": f"Unknown power action: {action}"}
        return {"action": "power_" + action,
                "summary": result.get("summary", f"{action.title()} initiated"),
                "details": result}
    except Exception as exc:
        logger.exception("Failed power action %s", action)
        return {"action": "power_" + action, "error": str(exc),
                "summary": f"Power {action} failed: {exc}"}


async def _execute_screenshot() -> dict[str, Any]:
    try:
        import pyautogui
        import io
        import base64
        screenshot = pyautogui.screenshot()
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return {"action": "screenshot",
                "summary": "Screenshot captured",
                "image_base64": b64}
    except Exception as exc:
        logger.exception("Failed to take screenshot")
        return {"action": "screenshot", "error": str(exc),
                "summary": f"Screenshot failed: {exc}"}


async def _execute_clipboard_read() -> dict[str, Any]:
    try:
        from dash_backend.services.clipboard import ClipboardService
        svc = ClipboardService()
        result = await svc.read()
        text = result.get("text", "")
        return {"action": "clipboard_read", "text": text,
                "summary": f"Clipboard: {text[:200]}" if text else "Clipboard is empty"}
    except Exception as exc:
        logger.exception("Failed to read clipboard")
        return {"action": "clipboard_read", "error": str(exc),
                "summary": f"Clipboard read failed: {exc}"}


async def _execute_clipboard_write(text: str) -> dict[str, Any]:
    try:
        from dash_backend.services.clipboard import ClipboardService
        svc = ClipboardService()
        result = await svc.write(text)
        return {"action": "clipboard_write", "text": text,
                "summary": f"Copied to clipboard: {text[:100]}"}
    except Exception as exc:
        logger.exception("Failed to write clipboard")
        return {"action": "clipboard_write", "error": str(exc),
                "summary": f"Clipboard write failed: {exc}"}
