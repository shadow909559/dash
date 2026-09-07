"""Browser tools - YouTube search, close tab, browser detection."""

from __future__ import annotations

import subprocess
import sys
import webbrowser
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"


class SearchYouTubeTool(BaseTool):
    name = "search_youtube"
    description = "Search YouTube for a query and open results in the default browser."
    parameters = [
        ToolParameter("query", "Search query", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="query required")
        try:
            encoded = subprocess.quote(query)
            url = f"https://www.youtube.com/results?search_query={encoded}"
            webbrowser.open(url)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"query": query, "url": url}, summary=f"Searching YouTube for: {query}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CloseBrowserTabTool(BaseTool):
    name = "close_browser_tab"
    description = "Close a browser tab by sending Ctrl+W. Best-effort on the active window."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "browser"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            import pyautogui
            pyautogui.hotkey("ctrl", "w")
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Closed active browser tab")
        except ImportError:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pyautogui required")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))
