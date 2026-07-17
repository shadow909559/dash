from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass

from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager
from .registry import SkillRegistry

logger = get_logger(__name__)


@dataclass
class SkillContext:
    user_id: Optional[str]
    session_id: Optional[str]
    extra: Dict[str, Any]


class SkillRouter:
    """Routes planner or parsed intents to registered skill services.

    The router does not execute tools itself — it delegates to each skill which
    must use the centralized ToolManager to run actions. This ensures permission
    checks and execution logging are preserved.
    """

    def __init__(self, tool_manager: Optional[ToolManager] = None):
        self.tool_manager = tool_manager or ToolManager.get_instance()
        self.registry = SkillRegistry.get()

    async def route(self, intent: str, args: Dict[str, Any], context: SkillContext) -> Dict[str, Any]:
        logger.info("Routing intent=%s args=%s", intent, args)
        skill_name = self.registry.match_skill_for_intent(intent)
        if not skill_name:
            # fallback to research/coding via planner decisions
            skill_name = "research"
        skill = self.registry.get_skill(skill_name)
        if not skill:
            logger.error("No skill registered for %s", skill_name)
            return {"status": "error", "error": "no_skill"}
        try:
            result = await skill.handle(intent=intent, args=args, context=context)
            return {"status": "ok", "result": result}
        except Exception as exc:
            logger.exception("skill execution failed")
            return {"status": "error", "error": str(exc)}
