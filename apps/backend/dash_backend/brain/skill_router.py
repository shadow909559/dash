"""Brain Skill Router - Routes tasks to appropriate skills.

Intelligently routes tasks to registered skills based on task
requirements, skill capabilities, and performance history.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.skills.registry import SkillRegistry
from dash_backend.skills.skill_router import SkillRouter as BaseSkillRouter, SkillContext
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


class BrainSkillRouter:
    """Enhanced skill router with learning and optimization.

    Features:
    - Skill matching based on intent and context
    - Performance tracking for skill selection
    - Fallback chain for skill failures
    - Skill composition for complex tasks
    - Cache for frequent intent-skill mappings
    """

    def __init__(self):
        self.tool_manager = get_tool_manager()
        self.base_router = BaseSkillRouter(self.tool_manager)
        self._routing_cache: Dict[str, str] = {}
        self._performance_history: Dict[str, List[bool]] = {}

    async def route(
        self,
        intent: str,
        args: Dict[str, Any],
        context: Optional[SkillContext] = None,
    ) -> Dict[str, Any]:
        """Route an intent to the appropriate skill.

        Args:
            intent: The task intent string
            args: Arguments for the skill
            context: Optional skill context

        Returns:
            Execution result dict with status and result
        """
        if context is None:
            context = SkillContext(
                user_id=None,
                session_id=None,
                extra={},
            )

        # Try cached routing first
        cache_key = self._get_cache_key(intent, context)
        cached_skill = self._routing_cache.get(cache_key)

        if cached_skill and SkillRegistry.get_skill(cached_skill):
            try:
                result = await self._execute_with_tracking(
                    cached_skill, intent, args, context
                )
                if result.get("status") == "ok":
                    return result
            except Exception:
                pass

        # Use base router
        try:
            result = await self.base_router.route(
                intent=intent, args=args, context=context
            )
            if result.get("status") == "ok":
                # Cache the successful routing
                skill_name = SkillRegistry.match_skill_for_intent(intent)
                if skill_name:
                    self._routing_cache[cache_key] = skill_name
                return result
        except Exception as exc:
            logger.warning("Base routing failed: %s", exc)

        # Try individual skills directly
        all_skills = SkillRegistry.list_skills()
        for skill_name in all_skills:
            if skill_name == cached_skill:
                continue  # Already tried
            try:
                result = await self._execute_with_tracking(
                    skill_name, intent, args, context
                )
                if result.get("status") == "ok":
                    self._routing_cache[cache_key] = skill_name
                    return result
            except Exception:
                continue

        return {"status": "error", "error": "no_skill_available"}

    async def _execute_with_tracking(
        self,
        skill_name: str,
        intent: str,
        args: Dict[str, Any],
        context: SkillContext,
    ) -> Dict[str, Any]:
        """Execute a skill and track its performance."""
        skill = SkillRegistry.get_skill(skill_name)
        if not skill:
            return {"status": "error", "error": f"skill_not_found: {skill_name}"}

        try:
            result = await skill.handle(intent=intent, args=args, context=context)
            self._record_performance(skill_name, True)
            return {"status": "ok", "result": result, "skill": skill_name}
        except Exception as exc:
            self._record_performance(skill_name, False)
            logger.warning("Skill %s failed: %s", skill_name, exc)
            return {"status": "error", "error": str(exc), "skill": skill_name}

    def _get_cache_key(self, intent: str, context: SkillContext) -> str:
        """Generate cache key for intent routing."""
        intent_key = intent.lower().strip()[:50]
        user_id = context.user_id or "system"
        return f"{user_id}:{intent_key}"

    def _record_performance(self, skill_name: str, success: bool):
        """Record skill execution performance."""
        if skill_name not in self._performance_history:
            self._performance_history[skill_name] = []
        history = self._performance_history[skill_name]
        history.append(success)
        # Keep only recent history
        if len(history) > 100:
            history.pop(0)

    def get_skill_reliability(self, skill_name: str) -> float:
        """Get reliability score for a skill based on history."""
        history = self._performance_history.get(skill_name, [])
        if not history:
            return 0.5
        return sum(history) / len(history)

    def clear_cache(self):
        """Clear the routing cache."""
        self._routing_cache.clear()
        self._performance_history.clear()