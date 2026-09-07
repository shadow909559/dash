"""Dash AI Agent - Tool Calling System.

Every tool implements the BaseTool interface and registers itself
with the ToolRegistry for dynamic discovery by the ToolManager.

Import tool modules here so ToolRegistry.discover() picks them up
when scanning the dash_backend.tools package.
"""

from __future__ import annotations

# Import all tool modules to ensure BaseTool subclasses are discovered
# by the ToolRegistry when it scans the tools package.
from dash_backend.tools import (
    ocr_tools,
    wifi_tools,
    bluetooth_tools,
    desktop_automation,
    desktop_windows_tools,
    device_tools,
    explorer_tools,
    file_tools,
    folder_tools,
    git_tools,
    keyboard_tools,
    mouse_tools,
    registry_tools,
    system_management_tools,
    system_tools,
    terminal_tool,
    terminal_tools,
    web_tools,
    window_management_tools,
    browser_tools,
    discovery_tools,
)
