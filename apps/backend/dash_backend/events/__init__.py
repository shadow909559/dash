"""Event Bus system for DASH AI OS.

Provides a publish/subscribe event system for all internal communication
between components. All system events flow through this bus including:
- Desktop events (window, process, clipboard, file)
- Browser events (tab, bookmark, navigation)
- Voice events (STT, TTS, wake word, VAD)
- Vision events (screen, camera, OCR)
- Memory events (save, retrieve, update, delete)
- AI events (reasoning, planning, execution)
- Automation events (trigger, execute, complete)
- Plugin events (load, unload, error)
- System events (startup, shutdown, health)
"""

from __future__ import annotations

from .event_bus import EventBus, Event, EventPriority, get_event_bus

__all__ = [
    "EventBus",
    "Event",
    "EventPriority",
    "get_event_bus",
]

