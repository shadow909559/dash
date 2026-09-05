"""Wi-Fi control tools for Windows using netsh and PowerShell.

Provides tools to enable/disable WiFi, scan networks, connect/disconnect,
and forget profiles. All tools return structured JSON.
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


# ── Helpers ──────────────────────────────────────────

def _run_netsh(args: list[str], timeout: int = 15) -> str:
    if not IS_WINDOWS:
        raise RuntimeError("Wi-Fi tools are Windows-only")
    result = subprocess.run(
        ["netsh"] + args, capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _run_powershell(script: str, timeout: int = 30) -> dict:
    if not IS_WINDOWS:
        raise RuntimeError("Wi-Fi tools are Windows-only")
    ps = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    out = ps.stdout.strip()
    if out:
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {"raw_output": out}
    if ps.returncode != 0:
        raise RuntimeError(ps.stderr.strip())
    return {}


def _parse_netsh_ssid_list(output: str) -> list[dict]:
    networks = []
    current: dict[str, Any] = {}
    for line in output.splitlines():
        line = line.strip()
        lower = line.lower()
        if lower.startswith("ssid"):
            if current:
                networks.append(current)
            current = {"ssid": line.split(":", 1)[-1].strip()}
        elif "bssid" in lower and current:
            current["bssid"] = line.split(":", 1)[-1].strip()
        elif "signal" in lower and current:
            sig = line.split(":", 1)[-1].strip().replace("%", "")
            try:
                current["signal_percent"] = int(sig)
            except ValueError:
                current["signal_percent"] = 0
        elif "authentication" in lower and current:
            current["auth"] = line.split(":", 1)[-1].strip()
        elif "channel" in lower and current:
            current["channel"] = line.split(":", 1)[-1].strip()
        elif "radio type" in lower and current:
            current["radio_type"] = line.split(":", 1)[-1].strip()
    if current:
        networks.append(current)
    return networks


# ── wifi_on ─────────────────────────────────────────

class WifiOnTool(BaseTool):
    name = "wifi_on"
    description = "Enable the Wi-Fi adapter on Windows."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            result = _run_powershell(
                "Get-NetAdapter -Name '*Wi-Fi*','*Wireless*','*WLAN*' -ErrorAction Stop | "
                "Enable-NetAdapter -Confirm:$false; "
                "Write-Output '{\"status\":\"enabled\"}'"
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary="Wi-Fi enabled")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── wifi_off ────────────────────────────────────────

class WifiOffTool(BaseTool):
    name = "wifi_off"
    description = "Disable the Wi-Fi adapter on Windows."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            result = _run_powershell(
                "Get-NetAdapter -Name '*Wi-Fi*','*Wireless*','*WLAN*' -ErrorAction Stop | "
                "Disable-NetAdapter -Confirm:$false; "
                "Write-Output '{\"status\":\"disabled\"}'"
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary="Wi-Fi disabled")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── scan_wifi ───────────────────────────────────────

class ScanWifiTool(BaseTool):
    name = "scan_wifi"
    description = "Scan for available Wi-Fi networks and return structured results."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = _run_netsh(["wlan", "show", "networks", "mode=bssid"])
            networks = _parse_netsh_ssid_list(output)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"networks": networks, "count": len(networks)},
                summary=f"Found {len(networks)} networks",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── current_wifi ────────────────────────────────────

class CurrentWifiTool(BaseTool):
    name = "current_wifi"
    description = "Show currently connected Wi-Fi network details."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = _run_netsh(["wlan", "show", "interfaces"])
            info: dict[str, Any] = {}
            for line in output.splitlines():
                line = line.strip()
                if ":" in line:
                    key, val = line.split(":", 1)
                    k = key.strip().lower().replace(" ", "_")
                    v = val.strip()
                    if k in ("ssid", "bssid", "state", "signal", "channel", "radio_type"):
                        info[k] = v
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=info,
                summary=f"Connected to: {info.get('ssid', 'None')}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── connect_wifi ────────────────────────────────────

class ConnectWifiTool(BaseTool):
    name = "connect_wifi"
    description = "Connect to a Wi-Fi network by SSID. Requires a saved profile."
    parameters = [
        ToolParameter("ssid", "SSID of the Wi-Fi network to connect to", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        ssid = kwargs.get("ssid", "")
        if not ssid:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="ssid required")
        try:
            output = _run_netsh(["wlan", "connect", f"name={ssid}"])
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"ssid": ssid, "output": output.strip()},
                summary=f"Connecting to {ssid}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── disconnect_wifi ─────────────────────────────────

class DisconnectWifiTool(BaseTool):
    name = "disconnect_wifi"
    description = "Disconnect from the current Wi-Fi network."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            output = _run_netsh(["wlan", "disconnect"])
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"output": output.strip()},
                summary="Disconnected from Wi-Fi",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


# ── forget_wifi ─────────────────────────────────────

class ForgetWifiTool(BaseTool):
    name = "forget_wifi"
    description = "Remove/forget a saved Wi-Fi profile."
    parameters = [
        ToolParameter("profile", "Profile name (SSID) to remove", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "wifi"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        profile = kwargs.get("profile", "")
        if not profile:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="profile required")
        try:
            output = _run_netsh(["wlan", "delete", "profile", f"name={profile}"])
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"profile": profile, "output": output.strip()},
                summary=f"Forgot profile: {profile}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

