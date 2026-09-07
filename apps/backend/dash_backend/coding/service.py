from __future__ import annotations

from typing import Dict, Any, Optional

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


class CodingSkill:
    name = "coding"

    def __init__(self, tool_manager: Optional[Any] = None):
        self.tool_manager = tool_manager or get_tool_manager()

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        logger.info("CodingSkill handling %s %s", intent, args)
        # Examples: run tests, build, run linters, create file, edit file
        if intent.startswith("run tests") or "test" in intent:
            return await self.tool_manager.execute("run_command", {"command": "pytest", "timeout": 60})
        if intent.startswith("build") or "build" in intent:
            return await self.tool_manager.execute("run_command", {"command": "npm run build", "timeout": 300})
        if intent.startswith("open file") or intent.startswith("edit"):
            path = args.get("path")
            if not path:
                return {"error": "no_path"}
            return await self.tool_manager.execute("open_application", {"path": path})
        return {"error": "unknown_coding_intent"}
