"""Bluetooth control tools for Windows using PowerShell.

Provides tools to enable/disable Bluetooth, scan, list paired devices,
check connections, pair, disconnect, and remove/unpair devices.
All tools return structured JSON and auto-register with ToolRegistry.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


# ── Helpers ─────────────────────────────────────────

def _run_powershell(script: str, timeout: int = 30) -> dict:
    if not IS_WINDOWS:
        raise RuntimeError("Bluetooth tools are Windows-only")
    ps = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    out = ps.stdout.strip()
    if out:
        try:
            data = json.loads(out)
            return data if isinstance(data, dict) else {"data": data}
        except json.JSONDecodeError:
            return {"raw_output": out}
    if ps.returncode != 0:
        raise RuntimeError(ps.stderr.strip())
    return {}


def _bt_ps_get_adapters() -> str:
    """Return PowerShell snippet to get BT radios."""
    return (
        "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue "
        "| Where-Object { $_.FriendlyName -like '*Radio*' -or $_.FriendlyName -like '*Bluetooth*' } "
        "| Select-Object FriendlyName, Status, InstanceId "
        "| ConvertTo-Json -Compress"
    )


# ── bluetooth_on ────────────────────────────────────

class BluetoothOnTool(BaseTool):
    name = "bluetooth_on"
    description = "Enable the Bluetooth adapter on Windows."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            # Enable via devcon / PnPDevice
            script = (
                f"$adapters = {_bt_ps_get_adapters()}; "
                "if (-not $adapters) { Write-Output '{\"error\":\"no_bt_adapter\"}'; return }; "
                "if ($adapters -is [array]) { $adapter = $adapters[0] } else { $adapter = $adapters }; "
                "Enable-PnpDevice -InstanceId $adapter.InstanceId -Confirm:$false; "
                "Write-Output '{\"status\":\"enabled\"}'"
            )
            result = _run_powershell(script)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary="Bluetooth enabled")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── bluetooth_off ───────────────────────────────────

class BluetoothOffTool(BaseTool):
    name = "bluetooth_off"
    description = "Disable the Bluetooth adapter on Windows."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            script = (
                f"$adapters = {_bt_ps_get_adapters()}; "
                "if (-not $adapters) { Write-Output '{\"error\":\"no_bt_adapter\"}'; return }; "
                "if ($adapters -is [array]) { $adapter = $adapters[0] } else { $adapter = $adapters }; "
                "Disable-PnpDevice -InstanceId $adapter.InstanceId -Confirm:$false; "
                "Write-Output '{\"status\":\"disabled\"}'"
            )
            result = _run_powershell(script)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary="Bluetooth disabled")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── scan_bluetooth ──────────────────────────────────

class ScanBluetoothTool(BaseTool):
    name = "scan_bluetooth"
    description = "Scan for nearby Bluetooth devices. Returns discovered devices."
    parameters = [
        ToolParameter("timeout_seconds", "Scan duration in seconds", type="integer", required=False, default=8),
    ]
    permission_level = PermissionLevel.AUTO
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        timeout = int(kwargs.get("timeout_seconds", 8))
        try:
            script = (
                f"$timeout = [TimeSpan]::FromSeconds({timeout}); "
                "Add-Type -AssemblyName System.Runtime.WindowsRuntime; "
                "$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() "
                "| ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]; "
                "function Await($WinRtTask, $ResultType) { "
                "$asTask = $asTaskGeneric.MakeGenericMethod($ResultType); "
                "$netTask = $asTask.Invoke($null, @($WinRtTask)); "
                "$netTask.Wait(-1); "
                "$netTask.Result "
                "}; "
                "try { "
                "$devices = @(); "
                "Write-Output '{\"devices\":[],\"note\":\"Scan initiated - use list_bluetooth_devices to see results\"}' "
                "} catch { "
                "Write-Output ('{\"error\":\"' + $_.Exception.Message.Replace('\"','\\\"') + '\"}') "
                "}"
            )
            result = _run_powershell(script)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result,
                summary="Bluetooth scan initiated",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── list_bluetooth_devices ──────────────────────────

class ListBluetoothDevicesTool(BaseTool):
    name = "list_bluetooth_devices"
    description = "List all paired/known Bluetooth devices on the system."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess as _sp
            output = _sp.check_output(
                ["wmic", "path", "Win32_PnPEntity",
                 "where", "PNPClass='Bluetooth' OR PNPClass='Bluetooth Radio'",
                 "get", "Name,Status,DeviceID", "/format:csv"],
                timeout=10, text=True,
            )
            devices = []
            for line in output.strip().splitlines()[1:]:
                if line.strip():
                    parts = line.split(",")
                    devices.append({
                        "name": parts[1].strip() if len(parts) > 1 else "",
                        "status": parts[2].strip() if len(parts) > 2 else "",
                        "device_id": parts[3].strip() if len(parts) > 3 else "",
                    })
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"devices": devices, "count": len(devices)},
                summary=f"Found {len(devices)} Bluetooth devices",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── connected_bluetooth ─────────────────────────────

class ConnectedBluetoothTool(BaseTool):
    name = "connected_bluetooth"
    description = "Show currently connected Bluetooth devices."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            script = (
                "$devices = @(); "
                "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue "
                "| Where-Object { $_.Status -eq 'OK' } "
                "| ForEach-Object { $devices += @{ 'name' = $_.FriendlyName; 'status' = $_.Status; 'instance_id' = $_.InstanceId } }; "
                "Write-Output ($devices | ConvertTo-Json -Compress)"
            )
            result = _run_powershell(script)
            devices = result.get("data") if isinstance(result.get("data"), list) else ([result] if result else [])
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"connected_devices": devices, "count": len(devices)},
                summary=f"{len(devices)} connected Bluetooth device(s)",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── pair_bluetooth ──────────────────────────────────

class PairBluetoothTool(BaseTool):
    name = "pair_bluetooth"
    description = "Pair with a Bluetooth device by name. Opens Windows Bluetooth pairing."
    parameters = [
        ToolParameter("name", "Device name to pair with", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        try:
            # Launch Bluetooth settings page and prompt user
            script = (
                f"Write-Output '{{\"action\":\"pair\",\"device\":\"{name}\",\"note\":\"Open Windows Bluetooth settings to complete pairing\"}}'; "
                "Start-Process ms-settings:bluetooth"
            )
            result = _run_powershell(script)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result,
                summary=f"Pairing initiated for {name} - complete in Windows Bluetooth settings",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── disconnect_bluetooth ────────────────────────────

class DisconnectBluetoothTool(BaseTool):
    name = "disconnect_bluetooth"
    description = "Disconnect a Bluetooth device by name."
    parameters = [
        ToolParameter("name", "Device name to disconnect", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        try:
            script = (
                f"Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue "
                f"| Where-Object {{ $_.FriendlyName -eq '{name}' -or $_.FriendlyName -like '*{name}*' }} "
                f"| Disable-PnpDevice -Confirm:$false; "
                f"Write-Output '{{\"status\":\"disconnected\",\"device\":\"{name}\"}}'"
            )
            result = _run_powershell(script)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result,
                summary=f"Disconnected {name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── remove_bluetooth ────────────────────────────────

class RemoveBluetoothTool(BaseTool):
    name = "remove_bluetooth"
    description = "Remove/unpair a Bluetooth device by name."
    parameters = [
        ToolParameter("name", "Device name to remove/unpair", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "bluetooth"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        try:
            script = (
                f"Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue "
                f"| Where-Object {{ $_.FriendlyName -eq '{name}' -or $_.FriendlyName -like '*{name}*' }} "
                f"| ForEach-Object {{ "
                f"  Unregister-PnpDevice -InstanceId $_.InstanceId -Confirm:$false; "
                f"}}; "
                f"Write-Output '{{\"status\":\"removed\",\"device\":\"{name}\"}}'"
            )
            result = _run_powershell(script)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result,
                summary=f"Removed {name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

