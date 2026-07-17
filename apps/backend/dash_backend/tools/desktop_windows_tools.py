from __future__ import annotations

import platform
import subprocess
import webbrowser
import os
import shlex
from typing import Any, Dict, List

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)

IS_WINDOWS = platform.system().lower() == "windows"


# Helper: safe subprocess run without shell injection
def _run_process(cmd: List[str], timeout: int = 10) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {"returncode": -1, "stdout": "", "stderr": f"timeout: {exc}"}
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": str(exc)}


# -------------------------
# Desktop tools
# -------------------------

class OpenApplicationTool(BaseTool):
    name = "open_application"
    description = "Open an application or executable by path."
    parameters = [
        ToolParameter("path", "Path to executable or app to open", required=True),
        ToolParameter("args", "Optional list of arguments", type="array", required=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path")
        args = kwargs.get("args") or []
        if not path:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="'path' required")
        try:
            # Use os.startfile on Windows, otherwise subprocess
            if IS_WINDOWS:
                os.startfile(path)
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"path": path}, summary=f"Opened {path}")
            else:
                cmd = [path] + (list(args) if isinstance(args, (list, tuple)) else [args])
                res = _run_process(cmd, timeout=30)
                status = ToolStatus.SUCCESS if res["returncode"] == 0 else ToolStatus.ERROR
                return ToolResult(tool_name=self.name, status=status, output=res, summary="Opened application (non-windows)")
        except Exception as exc:
            logger.exception("open_application failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CloseApplicationTool(BaseTool):
    name = "close_application"
    description = "Close an application by process id or image name."
    parameters = [
        ToolParameter("pid", "Process ID to terminate", required=False, type="integer"),
        ToolParameter("name", "Process image name to terminate (e.g., notepad.exe)", required=False),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        pid = kwargs.get("pid")
        name = kwargs.get("name")
        try:
            if IS_WINDOWS:
                if pid:
                    res = _run_process(["taskkill", "/PID", str(int(pid)), "/F"], timeout=10)
                elif name:
                    res = _run_process(["taskkill", "/IM", str(name), "/F"], timeout=10)
                else:
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pid or name required")
                status = ToolStatus.SUCCESS if res["returncode"] == 0 else ToolStatus.ERROR
                return ToolResult(tool_name=self.name, status=status, output=res, summary="Closed application")
            else:
                # POSIX
                if pid:
                    res = _run_process(["kill", "-TERM", str(int(pid))], timeout=10)
                elif name:
                    res = _run_process(["pkill", "-f", str(name)], timeout=10)
                else:
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pid or name required")
                status = ToolStatus.SUCCESS if res["returncode"] == 0 else ToolStatus.ERROR
                return ToolResult(tool_name=self.name, status=status, output=res, summary="Closed application")
        except Exception as exc:
            logger.exception("close_application failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RestartApplicationTool(BaseTool):
    name = "restart_application"
    description = "Restart an application by name or path. Requires confirmation."
    parameters = [
        ToolParameter("path", "Optional path to executable to start after closing", required=False),
        ToolParameter("name", "Optional process image name to restart (e.g., app.exe)", required=False),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name")
        path = kwargs.get("path")
        # Attempt best-effort: close by name then open path
        try:
            if name:
                close_tool = CloseApplicationTool()
                close_res = await close_tool.execute(context, name=name)
                if close_res.is_error:
                    return close_res
            if path:
                open_tool = OpenApplicationTool()
                open_res = await open_tool.execute(context, path=path)
                return open_res
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Restart invoked (no path provided)")
        except Exception as exc:
            logger.exception("restart_application failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListProcessesTool(BaseTool):
    name = "list_running_processes"
    description = "List running processes on the system (limited output)."
    parameters = [ToolParameter("limit", "Maximum number of processes to return", required=False, type="integer", default=50)]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 50))
        try:
            if IS_WINDOWS:
                res = _run_process(["tasklist"], timeout=10)
                out = res.get("stdout", "")
                lines = out.splitlines()
                # return first N lines (best-effort)
                data = lines[: limit + 10]
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"lines": data}, summary="Listed processes")
            else:
                res = _run_process(["ps", "-aux"], timeout=10)
                lines = res.get("stdout", "").splitlines()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"lines": lines[:limit]}, summary="Listed processes")
        except Exception as exc:
            logger.exception("list_running_processes failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class BringWindowToFrontTool(BaseTool):
    name = "bring_window_to_front"
    description = "Bring a window with a matching title substring to the foreground."
    parameters = [ToolParameter("title", "Substring of window title to match", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title")
        if not title:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="title required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="bring_window_to_front only supported on Windows")
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            EnumWindows = user32.EnumWindows
            EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            GetWindowTextLength = user32.GetWindowTextLengthW
            GetWindowText = user32.GetWindowTextW
            IsWindowVisible = user32.IsWindowVisible

            matches = []

            def foreach_window(hwnd, lParam):
                if not IsWindowVisible(hwnd):
                    return True
                length = GetWindowTextLength(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                text = buff.value
                if title.lower() in text.lower():
                    matches.append(hwnd)
                    return False  # stop enumeration on first match
                return True

            EnumWindows(EnumWindowsProc(foreach_window), 0)
            if not matches:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="No window matched")
            hwnd = matches[0]
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"hwnd": int(hwnd)}, summary="Brought window to front")
        except Exception as exc:
            logger.exception("bring_window_to_front failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# -------------------------
# Browser tools
# -------------------------

class OpenURLTool(BaseTool):
    name = "open_url"
    description = "Open a URL in the default browser."
    parameters = [ToolParameter("url", "URL to open", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url")
        if not url:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="url required")
        try:
            webbrowser.open(url)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"url": url}, summary="Opened URL")
        except Exception as exc:
            logger.exception("open_url failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SearchWebTool(BaseTool):
    name = "search_web"
    description = "Search the web using the default browser with a query string."
    parameters = [ToolParameter("query", "Search query", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query")
        if not query:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="query required")
        try:
            url = "https://www.google.com/search?q=" + subprocess.quote(query)
            webbrowser.open(url)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"query": query, "url": url}, summary="Opened search")
        except Exception as exc:
            logger.exception("search_web failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class OpenTabTool(OpenURLTool):
    name = "open_tab"
    description = "Open a new browser tab with the given URL."
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        url = kwargs.get("url")
        try:
            webbrowser.open_new_tab(url)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"url": url}, summary="Opened new tab")
        except Exception as exc:
            logger.exception("open_tab failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CloseTabTool(BaseTool):
    name = "close_tab"
    description = "Close a browser tab matching a URL or title (best-effort). May be restricted."
    parameters = [ToolParameter("match", "URL or title substring to match", required=True)]
    permission_level = PermissionLevel.RESTRICTED
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="close_tab not implemented for general browsers; consider using a browser extension or automation")


class RefreshTabTool(BaseTool):
    name = "refresh_tab"
    description = "Refresh a browser tab matching URL or title (best-effort). May be restricted."
    parameters = [ToolParameter("match", "URL or title substring to match", required=True)]
    permission_level = PermissionLevel.RESTRICTED
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="refresh_tab not implemented for general browsers; consider using a browser extension or automation")


# -------------------------
# Clipboard tools (Windows implemented via ctypes)
# -------------------------

class CopyTextTool(BaseTool):
    name = "copy_text"
    description = "Copy text to the system clipboard."
    parameters = [ToolParameter("text", "Text to copy", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        text = kwargs.get("text", "")
        try:
            if IS_WINDOWS:
                import ctypes
                from ctypes import wintypes

                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                if not user32.OpenClipboard(None):
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="OpenClipboard failed")
                user32.EmptyClipboard()
                hGlobalMem = kernel32.GlobalAlloc(0x0002, (len(text) + 1) * 2)
                lpGlobalMem = kernel32.GlobalLock(hGlobalMem)
                ctypes.memmove(lpGlobalMem, text.encode("utf-16le"), len(text) * 2)
                kernel32.GlobalUnlock(hGlobalMem)
                user32.SetClipboardData(CF_UNICODETEXT, hGlobalMem)
                user32.CloseClipboard()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Text copied to clipboard")
            else:
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Text copied (pyperclip)")
                except Exception:
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Clipboard not supported on this platform (pyperclip missing)")
        except Exception as exc:
            logger.exception("copy_text failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ReadClipboardTool(BaseTool):
    name = "read_clipboard"
    description = "Read text from the system clipboard."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            if IS_WINDOWS:
                import ctypes
                from ctypes import wintypes

                CF_UNICODETEXT = 13
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32

                if not user32.OpenClipboard(None):
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="OpenClipboard failed")
                handle = user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    user32.CloseClipboard()
                    return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"text": ""}, summary="Clipboard empty")
                lpwcstr = kernel32.GlobalLock(handle)
                size = kernel32.GlobalSize(handle)
                raw = ctypes.create_string_buffer(size)
                ctypes.memmove(raw, lpwcstr, size)
                kernel32.GlobalUnlock(handle)
                user32.CloseClipboard()
                text = raw.raw.decode("utf-16le", errors="ignore").rstrip("\x00")
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"text": text}, summary="Read clipboard text")
            else:
                try:
                    import pyperclip
                    text = pyperclip.paste()
                    return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"text": text}, summary="Read clipboard (pyperclip)")
                except Exception:
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Clipboard not supported on this platform (pyperclip missing)")
        except Exception as exc:
            logger.exception("read_clipboard failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ClearClipboardTool(BaseTool):
    name = "clear_clipboard"
    description = "Clear the system clipboard."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            if IS_WINDOWS:
                import ctypes
                user32 = ctypes.windll.user32
                if not user32.OpenClipboard(None):
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="OpenClipboard failed")
                user32.EmptyClipboard()
                user32.CloseClipboard()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Clipboard cleared")
            else:
                try:
                    import pyperclip
                    pyperclip.copy("")
                    return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Clipboard cleared (pyperclip)")
                except Exception:
                    return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Clipboard clear not supported on this platform (pyperclip missing)")
        except Exception as exc:
            logger.exception("clear_clipboard failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# -------------------------
# Notifications
# -------------------------

class ShowMessageTool(BaseTool):
    name = "show_message"
    description = "Show a modal message box on the desktop (Windows MessageBox)."
    parameters = [ToolParameter("title", "Message title", required=False, default="Dash"), ToolParameter("message", "Message body", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title", "Dash")
        message = kwargs.get("message", "")
        try:
            if IS_WINDOWS:
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, str(message), str(title), 0)
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Message shown")
            else:
                logger.info("show_message: %s - %s", title, message)
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Message logged")
        except Exception as exc:
            logger.exception("show_message failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class PlaySoundTool(BaseTool):
    name = "play_sound"
    description = "Play a short system sound on the client machine (best-effort)."
    parameters = [ToolParameter("sound", "Sound identifier or path", required=False)]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        snd = kwargs.get("sound")
        try:
            if IS_WINDOWS:
                import winsound
                if snd:
                    if os.path.isfile(snd):
                        winsound.PlaySound(snd, winsound.SND_FILENAME | winsound.SND_ASYNC)
                    else:
                        winsound.MessageBeep()
                else:
                    winsound.MessageBeep()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Sound played")
            else:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="play_sound not implemented on this platform")
        except Exception as exc:
            logger.exception("play_sound failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# -------------------------
# System info
# -------------------------

class SystemInfoTool(BaseTool):
    name = "system_info"
    description = "Return basic system information and resource usage."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            import platform as _platform
            info = {"platform": _platform.platform(), "processor": _platform.processor()}
            try:
                import psutil
                info.update({
                    "cpu_percent": psutil.cpu_percent(interval=0.1),
                    "memory": psutil.virtual_memory()._asdict(),
                    "disk": {p.mountpoint: psutil.disk_usage(p.mountpoint)._asdict() for p in psutil.disk_partitions()},
                })
            except Exception:
                try:
                    import shutil
                    total, used, free = shutil.disk_usage(".")
                    info.update({"disk_total": total, "disk_free": free})
                except Exception:
                    pass
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=info, summary="System info")
        except Exception as exc:
            logger.exception("system_info failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# -------------------------
# Run command (whitelisted)
# -------------------------

_WHITELIST = {"ipconfig", "ping", "tasklist", "whoami", "netstat", "dir"}

class RunCommandTool(BaseTool):
    name = "run_command"
    description = "Run a whitelisted command and capture stdout/stderr."
    parameters = [
        ToolParameter("command", "Command to run (first token must be whitelisted)", required=True),
        ToolParameter("timeout", "Timeout seconds", required=False, type="integer", default=10),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        cmd = kwargs.get("command")
        timeout = int(kwargs.get("timeout", 10))
        if not cmd:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="command required")
        try:
            parts = shlex.split(cmd)
        except Exception:
            parts = [cmd]
        if not parts:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="empty command")
        base = parts[0].lower()
        if base not in _WHITELIST:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Command '{base}' not allowed")
        try:
            proc = subprocess.run(parts, capture_output=True, text=True, timeout=timeout)
            output = {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
            status = ToolStatus.SUCCESS if proc.returncode == 0 else ToolStatus.ERROR
            return ToolResult(tool_name=self.name, status=status, output=output, summary="Command executed")
        except subprocess.TimeoutExpired as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.TIMEOUT, error_message=str(exc))
        except Exception as exc:
            logger.exception("run_command failed")
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# Note: additional features (mouse/keyboard/screenshot) intentionally omitted here
# to avoid heavy OS-specific dependencies; they can be added later behind a
# configuration toggle and with clear user consent.
