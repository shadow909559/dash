from __future__ import annotations

from typing import Dict, Any, Optional
from dataclasses import dataclass

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class SkillInterface:
    name: str

    async def handle(self, intent: str, args: Dict[str, Any], context: Any) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class _Registry:
    skills: Dict[str, SkillInterface]


_registry: Optional[_Registry] = None


class SkillRegistry:
    @classmethod
    def get(cls) -> _Registry:
        global _registry
        if _registry is None:
            _registry = _Registry(skills={})
        return _registry

    @classmethod
    def register(cls, skill: SkillInterface) -> None:
        r = cls.get()
        if getattr(skill, "name", None) is None:
            raise ValueError("Skill must have a name")
        r.skills[skill.name] = skill
        logger.info("Registered skill %s", skill.name)

    @classmethod
    def get_skill(cls, name: str) -> Optional[SkillInterface]:
        return cls.get().skills.get(name)

    @classmethod
    def match_skill_for_intent(cls, intent: str) -> Optional[str]:
        # Simple heuristic mapping
        i = intent.lower()
        if i.startswith("open") or i.startswith("close") or "window" in i:
            return "desktop"
        if i.startswith("search") or i.startswith("find"):
            return "browser"
        if i.startswith("run") or i.startswith("build") or i.startswith("test"):
            return "coding"
        if i.startswith("read") or i.startswith("ocr") or "screenshot" in i:
            return "vision"
        if i.startswith("call") or i.startswith("sms") or i.startswith("phone"):
            return "phone"
        return None
