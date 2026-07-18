"""Skill router and skill packages for Desktop AI Operating System.

This package provides a SkillRouter that receives planner assignments or parsed
voice intents and routes execution to specialized skill services (desktop,
vision, browser, coding, phone). Each skill implements a minimal service
interface and executes through the existing ToolManager to ensure central
permissioning and logging.

These are lightweight scaffolds to enable incremental implementation without
changing existing APIs or the WebSocket flow. Integrate the router into the
planner or websocket handlers to enable voice-first skill invocation.
"""
from .skill_router import SkillRouter
from .registry import SkillRegistry

__all__ = ["SkillRouter", "SkillRegistry"]
