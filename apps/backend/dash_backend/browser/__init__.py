"""Browser skill package: abstracts browser automation and web research.

Uses tools and browser automation plugins (Selenium, Playwright) via the
ToolManager. Default stubs keep the system functional without heavy
dependencies.
"""
from .service import BrowserSkill

__all__ = ["BrowserSkill"]
