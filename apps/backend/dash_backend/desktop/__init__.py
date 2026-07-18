"""Desktop skill package: interacts with the OS via ToolManager.

This package provides a DesktopSkill service that routes desktop-related
intents through ToolManager so all execution uses the central tool framework.
"""
from .service import DesktopSkill

__all__ = ["DesktopSkill"]
