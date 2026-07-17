from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager
from dash_backend.tools.tool_registry import ToolRegistry

logger = get_logger(__name__)


class DesktopSkill:
    name = "desktop"

    def __init__(self, tool_manager: Optional[Any] = None):
        self.tool_manager = tool_manager or get_tool_manager()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """Handle desktop-related intents by translating them into tool calls.

        This method keeps translation minimal and delegates to ToolManager to
        execute safe, registered tools (e.g., open_application, close_application,
        list_running_processes, bring_window_to_front, etc.).
        """
        logger.info("DesktopSkill handling %s %s", intent, args)
        # Basic mappings
        if intent.startswith("open"):
            target = args.get("target") or args.get("path")
            if not target:
                return {"error": "no target"}
            # prefer open_application tool
            return await self.tool_manager.execute("open_application", {"path": target})
        if intent.startswith("close"):
            name = args.get("name") or args.get("target")
            if not name:
                return {"error": "no process"}
            return await self.tool_manager.execute("close_application", {"name": name})
        if "process" in intent or "list" in intent:
            return await self.tool_manager.execute("list_running_processes", {"limit": 50})
        if "bring" in intent or "focus" in intent or "window" in intent:
            title = args.get("title") or args.get("target")
            if not title:
                return {"error": "no title"}
            return await self.tool_manager.execute("bring_window_to_front", {"title": title})
        # default
        return {"error": "unknown_desktop_intent"}
