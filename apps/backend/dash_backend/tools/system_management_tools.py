"""System management tools for Windows: startup apps, env vars, fonts, wifi, updates, services, display, network, task scheduler."""

from __future__ import annotations

import sys
import subprocess
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


def _run_wmic(query: str, timeout: int = 10) -> str:
    """Run a WMIC command and return stdout."""
    if not IS_WINDOWS:
        return ""
    try:
        result = subprocess.run(
            ["wmic"] + query.split(),
            capture_output=True, text=True, timeout=timeout,
        )
        return result.stdout
    except Exception:
        return ""


class StartupAppsTool(BaseTool):
    name = "list_startup_apps"
    description = "List all startup applications configured to run on system boot."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"apps": []}, summary="Not supported on this platform")
        try:
            output = _run_wmic('startup get caption,command,user /format:csv')
            apps = []
            for line in output.splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 3:
                        apps.append({
                            "caption": parts[1].strip() if len(parts) > 1 else "",
                            "command": parts[2].strip() if len(parts) > 2 else "",
                            "user": parts[3].strip() if len(parts) > 3 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"apps": apps}, summary=f"Found {len(apps)} startup apps")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class EnvironmentVariablesTool(BaseTool):
    name = "list_environment_variables"
    description = "List system and user environment variables."
    parameters = [
        ToolParameter("scope", "Scope: 'system', 'user', or 'all'", required=False, default="all"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        import os
        scope = kwargs.get("scope", "all")
        try:
            env = dict(os.environ)
            result = {}
            if scope in ("all", "system"):
                result["system"] = {k: v for k, v in env.items() if k.isupper()}
            if scope in ("all", "user"):
                result["user"] = {k: v for k, v in env.items() if not k.isupper()}
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=f"Returned {len(env)} variables")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class InstalledFontsTool(BaseTool):
    name = "list_installed_fonts"
    description = "List installed fonts on the system."
    parameters = [ToolParameter("limit", "Maximum fonts to return", type="integer", required=False, default=100)]
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 100))
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import winreg
            fonts = []
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
            for i in range(winreg.QueryInfoKey(key)[1]):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    fonts.append({"name": name, "file": value})
                except Exception:
                    pass
                if len(fonts) >= limit:
                    break
            winreg.CloseKey(key)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"fonts": fonts}, summary=f"Found {len(fonts)} fonts")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class WifiProfilesTool(BaseTool):
    name = "list_wifi_profiles"
    description = "List saved WiFi profiles on the system."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "network"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = subprocess.check_output(
                ["netsh", "wlan", "show", "profiles"],
                timeout=10, text=True,
            )
            profiles = []
            for line in output.splitlines():
                if "All User Profile" in line or "User Profile" in line:
                    name = line.split(":")[-1].strip()
                    if name:
                        profiles.append({"name": name})
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"profiles": profiles}, summary=f"Found {len(profiles)} WiFi profiles")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class WindowsUpdatesStatusTool(BaseTool):
    name = "windows_updates_status"
    description = "Check Windows Update status and list recent updates."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = _run_wmic('qfe get HotFixID,InstalledOn,Description /format:csv')
            updates = []
            for line in output.splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 3:
                        updates.append({
                            "hotfix_id": parts[1].strip() if len(parts) > 1 else "",
                            "installed_on": parts[2].strip() if len(parts) > 2 else "",
                            "description": parts[3].strip() if len(parts) > 3 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"updates": updates}, summary=f"Found {len(updates)} installed updates")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ServicesListTool(BaseTool):
    name = "list_services"
    description = "List Windows services with status."
    parameters = [
        ToolParameter("status", "Filter by status: 'running', 'stopped', or 'all'", required=False, default="all"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        status_filter = kwargs.get("status", "all")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = _run_wmic('service get Name,DisplayName,State,StartMode /format:csv')
            services = []
            for line in output.splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 4:
                        state = parts[3].strip() if len(parts) > 3 else ""
                        if status_filter != "all" and state.lower() != status_filter.lower():
                            continue
                        services.append({
                            "name": parts[1].strip() if len(parts) > 1 else "",
                            "display_name": parts[2].strip() if len(parts) > 2 else "",
                            "state": state,
                            "start_mode": parts[4].strip() if len(parts) > 4 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"services": services}, summary=f"Found {len(services)} services")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ServiceControlTool(BaseTool):
    name = "control_service"
    description = "Start, stop, restart, or pause a Windows service. Requires confirmation."
    parameters = [
        ToolParameter("name", "Service name", required=True),
        ToolParameter("action", "Action: start, stop, restart, pause, resume", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name")
        action = kwargs.get("action")
        if not name or not action:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name and action required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            cmd_map = {
                "start": ["net", "start", name],
                "stop": ["net", "stop", name],
                "restart": ["net", "stop", name, "&&", "net", "start", name],
                "pause": ["net", "pause", name],
                "resume": ["net", "continue", name],
            }
            cmd = cmd_map.get(action)
            if not cmd:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Unknown action: {action}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"service": name, "action": action}, summary=f"Service '{name}' {action}ed")
            else:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, output={"stderr": result.stderr}, error_message=f"Failed to {action} service: {result.stderr.strip()}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class DisplaySettingsTool(BaseTool):
    name = "get_display_settings"
    description = "Get display/screen settings: resolution, refresh rate, multiple monitors."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32

            monitors = []
            MONITORINFOF_PRIMARY = 1

            class MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD),
                ]

            def monitor_enum_proc(hmonitor, hdc, lprect, lparam):
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(MONITORINFO)
                ctypes.windll.user32.GetMonitorInfoW(hmonitor, ctypes.byref(info))
                
                monitors.append({
                    "handle": int(hmonitor),
                    "left": info.rcMonitor.left, "top": info.rcMonitor.top,
                    "right": info.rcMonitor.right, "bottom": info.rcMonitor.bottom,
                    "width": info.rcMonitor.right - info.rcMonitor.left,
                    "height": info.rcMonitor.bottom - info.rcMonitor.top,
                    "primary": bool(info.dwFlags & MONITORINFOF_PRIMARY),
                })
                return True
            
            MONITOR_ENUM_PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(wintypes.RECT), ctypes.c_void_p)
            user32.EnumDisplayMonitors(None, None, MONITOR_ENUM_PROC(monitor_enum_proc), 0)

            primary_display = next((m for m in monitors if m["primary"]), monitors[0]) if monitors else None

            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                "primary_display": primary_display,
                "multiple_monitors": len(monitors) > 1,
                "displays": monitors,
            }, summary="Display settings retrieved")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class NetworkAdaptersTool(BaseTool):
    name = "list_network_adapters"
    description = "List network adapters with status and configuration."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "network"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = _run_wmic('nic get Name,NetEnabled,MACAddress,Speed /format:csv')
            adapters = []
            for line in output.splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 4:
                        adapters.append({
                            "name": parts[1].strip() if len(parts) > 1 else "",
                            "mac_address": parts[3].strip() if len(parts) > 3 else "",
                            "enabled": parts[2].strip() if len(parts) > 2 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"adapters": adapters}, summary=f"Found {len(adapters)} adapters")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class TaskSchedulerListTool(BaseTool):
    name = "list_scheduled_tasks"
    description = "List scheduled tasks from Task Scheduler."
    parameters = [ToolParameter("limit", "Max tasks to return", type="integer", required=False, default=50)]
    permission_level = PermissionLevel.AUTO
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 50))
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = subprocess.check_output(
                ["schtasks", "/query", "/fo", "CSV", "/v"],
                timeout=15, text=True,
            )
            tasks = []
            for line in output.splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        tasks.append({
                            "task_name": parts[0].strip().strip('"'),
                            "status": parts[1].strip().strip('"') if len(parts) > 1 else "",
                        })
                if len(tasks) >= limit:
                    break
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"tasks": tasks}, summary=f"Found {len(tasks)} scheduled tasks")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))