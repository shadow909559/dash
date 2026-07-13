"""Automation task types (scaffold)."""

from enum import Enum


class AutomationKind(str, Enum):
    """Supported automation categories."""

    BROWSER = "browser"
    COMPUTER = "computer"
