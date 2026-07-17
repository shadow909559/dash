from __future__ import annotations

from typing import Dict, Any, Optional

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


class BrowserSkill:
    name = "browser"

    def __init__(self, tool_manager: Optional[Any] = None):
        self.tool_manager = tool_manager or get_tool_manager()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        logger.info("BrowserSkill handling %s %s", intent, args)
        if intent.startswith("search"):
            q = args.get("query") or args.get("text")
            if not q:
                return {"error": "no_query"}
            # Use system's search_web tool
            return await self.tool_manager.execute("search_web", {"query": q})
        if intent.startswith("open") and args.get("target"):
            return await self.tool_manager.execute("open_url", {"url": args.get("target")})
        return {"error": "unknown_browser_intent"}
