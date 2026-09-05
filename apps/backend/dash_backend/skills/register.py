from __future__ import annotations

from dash_backend.logging_config import get_logger
from .registry import SkillRegistry

logger = get_logger(__name__)

# Import skill implementations
from dash_backend.desktop.service import DesktopSkill
from dash_backend.vision.service import VisionSkill
from dash_backend.browser.service import BrowserSkill
from dash_backend.coding.service import CodingSkill
from dash_backend.phone.service import PhoneSkill


def register_skills() -> None:
    try:
        registry = SkillRegistry.get()
        # instantiate services
        skills = [DesktopSkill(), VisionSkill(), BrowserSkill(), CodingSkill(), PhoneSkill()]
        for s in skills:
            if registry.skills.get(s.name) is None:
                SkillRegistry.register(s)
    except Exception:
        logger.exception("Failed to register skills")


# Run registration on import
register_skills()
