"""DASH Companion Hub.

Tracks connected Android companions and enables desktop <-> phone routing.
The hub is a lightweight in-memory registry of companion devices that have
registered via WebSocket. Additive — does not replace the ADB service or the
Android app internals.
"""

from dash_backend.companion.hub import (
    CompanionDevice,
    CompanionHub,
    get_companion_hub,
)

__all__ = ["CompanionDevice", "CompanionHub", "get_companion_hub"]
