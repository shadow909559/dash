"""Registry tools - safe read-only Windows registry access."""

from __future__ import annotations

import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"

# Predefined safe registry paths for read-only access
SAFE_REGISTRY_PATHS = {
    "hkcu\\software\\microsoft\\windows\\currentversion\\run": "HKEY_CURRENT_USER",
    "hklm\\software\\microsoft\\windows\\currentversion\\run": "HKEY_LOCAL_MACHINE",
    "hklm\\software\\microsoft\\windows nt\\currentversion\\fonts": "HKEY_LOCAL_MACHINE",
    "hklm\\hardware\\devicemap\\keyboard": "HKEY_LOCAL_MACHINE",
    "hklm\\software\\microsoft\\windows\\currentversion\\uninstall": "HKEY_LOCAL_MACHINE",
    "hkcu\\control panel\\desktop": "HKEY_CURRENT_USER",
    "hklm\\system\\currentcontrolset\\services": "HKEY_LOCAL_MACHINE",
    "hkcu\\software\\microsoft\\windows\\currentversion\\explorer\\mountpoints2": "HKEY_CURRENT_USER",
}


class ReadRegistryTool(BaseTool):
    name = "read_registry"
    description = "Read values from a safe Windows registry path. Only read-only access to predefined safe paths."
    parameters = [
        ToolParameter("path", "Registry path (e.g., 'HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run')", required=True),
        ToolParameter("key", "Specific key name to read (optional, returns all values if omitted)", required=False),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", "").strip().lower()
        key_name = kwargs.get("key", "").strip()
        if not path:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")

        # Check if path is in safe list
        is_safe = False
        for safe_path in SAFE_REGISTRY_PATHS:
            if safe_path in path:
                is_safe = True
                break
        if not is_safe:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Registry path not in safe list: {path}")

        try:
            import winreg
            # Map root key
            root_map = {
                "hkcu": winreg.HKEY_CURRENT_USER,
                "hklm": winreg.HKEY_LOCAL_MACHINE,
                "hkcr": winreg.HKEY_CLASSES_ROOT,
                "hku": winreg.HKEY_USERS,
                "hkcc": winreg.HKEY_CURRENT_CONFIG,
            }
            parts = path.replace("\\", "/").split("/")
            root_key = root_map.get(parts[0]) if parts else None
            if root_key is None:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Unknown root key: {parts[0] if parts else ''}")

            sub_key = "\\".join(parts[1:])
            with winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_READ) as key:
                if key_name:
                    # Read specific value
                    try:
                        value, reg_type = winreg.QueryValueEx(key, key_name)
                        return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                            "path": path, "key": key_name,
                            "value": str(value), "type": _reg_type_name(reg_type),
                        }, summary=f"Read registry key '{key_name}'")
                    except FileNotFoundError:
                        return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Key not found: {key_name}")
                else:
                    # Enumerate all values
                    values = []
                    try:
                        for i in range(winreg.QueryInfoKey(key)[1]):
                            try:
                                name, value, reg_type = winreg.EnumValue(key, i)
                                values.append({
                                    "name": name,
                                    "value": str(value)[:500],
                                    "type": _reg_type_name(reg_type),
                                })
                            except Exception:
                                pass
                    except Exception:
                        pass
                    return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                        "path": path, "values": values, "count": len(values),
                    }, summary=f"Read {len(values)} values from registry")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


def _reg_type_name(t: int) -> str:
    types = {
        1: "REG_SZ", 2: "REG_EXPAND_SZ", 3: "REG_BINARY",
        4: "REG_DWORD", 7: "REG_MULTI_SZ", 11: "REG_QWORD",
    }
    return types.get(t, f"REG_UNKNOWN({t})")
