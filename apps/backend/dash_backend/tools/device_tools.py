"""Device management tools - audio, bluetooth, USB, printers, display info."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"


class ListAudioDevicesTool(BaseTool):
    name = "list_audio_devices"
    description = "List all audio input/output devices on the system."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "devices"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            output_result = subprocess.run(
                ["wmic", "path", "Win32_SoundDevice", "get", "Name,Status,Manufacturer", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout
            devices = []
            for line in output.strip().splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        devices.append({
                            "name": parts[1].strip() if len(parts) > 1 else "",
                            "status": parts[2].strip() if len(parts) > 2 else "",
                            "manufacturer": parts[3].strip() if len(parts) > 3 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"devices": devices},
                              summary=f"Found {len(devices)} audio devices")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListUsbDevicesTool(BaseTool):
    name = "list_usb_devices"
    description = "List all connected USB devices."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "devices"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            output_result = subprocess.run(
                ["wmic", "path", "Win32_USBControllerDevice", "get", "Dependent", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout
            devices = []
            for line in output.splitlines():
                if "Win32_PnPEntity" in line:
                    parts = line.split("=")
                    if len(parts) >= 2:
                        name = parts[-1].strip().replace('"', '').strip()
                        if name and name not in [d["name"] for d in devices]:
                            devices.append({"name": name})
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"devices": devices},
                              summary=f"Found {len(devices)} USB devices")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListPrintersTool(BaseTool):
    name = "list_printers"
    description = "List all installed printers on the system."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "devices"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            output_result = subprocess.run(
                ["wmic", "path", "Win32_Printer", "get", "Name,Status,Default,DriverName", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout
            printers = []
            for line in output.strip().splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        printers.append({
                            "name": parts[1].strip() if len(parts) > 1 else "",
                            "status": parts[2].strip() if len(parts) > 2 else "",
                            "is_default": parts[3].strip().upper() == "TRUE" if len(parts) > 3 else False,
                            "driver": parts[4].strip() if len(parts) > 4 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"printers": printers},
                              summary=f"Found {len(printers)} printers")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListBluetoothDevicesTool(BaseTool):
    name = "list_bluetooth_devices"
    description = "List paired Bluetooth devices."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "devices"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            output_result = subprocess.run(
                ["wmic", "path", "Win32_PnPEntity", "where", "PNPClass='Bluetooth' OR PNPClass='Bluetooth Radio'",
                 "get", "Name,Status", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout
            devices = []
            for line in output.strip().splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        devices.append({
                            "name": parts[1].strip() if len(parts) > 1 else "",
                            "status": parts[2].strip() if len(parts) > 2 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"devices": devices},
                              summary=f"Found {len(devices)} Bluetooth devices")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListDisplaysTool(BaseTool):
    name = "list_displays"
    description = "List connected display monitors with details."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "devices"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            output_result = subprocess.run(
                ["wmic", "path", "Win32_DesktopMonitor", "get", "Name,MonitorType,Status,ScreenWidth,ScreenHeight", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            output = output_result.stdout
            displays = []
            for line in output.strip().splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    if len(parts) >= 2:
                        displays.append({
                            "name": parts[1].strip() if len(parts) > 1 else "",
                            "monitor_type": parts[2].strip() if len(parts) > 2 else "",
                            "status": parts[3].strip() if len(parts) > 3 else "",
                        })
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"displays": displays},
                              summary=f"Found {len(displays)} displays")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))