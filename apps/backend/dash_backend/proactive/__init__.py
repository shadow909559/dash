"""DASH Proactive Intelligence layer (DASH 2.0, sections 5-7).

- signals.py   — detectors that turn environment context into suggestions
- state.py     — persistent cooldowns + shown history (never annoying)
- engine.py    — gating (threshold, dedup, cooldown, quiet hours, disable)
- briefing.py  — daily briefing + end-of-day summary with memory storage
"""

from dash_backend.proactive.engine import ProactiveEngine, get_proactive_engine, DEFAULT_CONFIG
from dash_backend.proactive.signals import Signal, detect_signals
from dash_backend.proactive.briefing import build_briefing, build_end_of_day

__all__ = [
    "ProactiveEngine",
    "get_proactive_engine",
    "DEFAULT_CONFIG",
    "Signal",
    "detect_signals",
    "build_briefing",
    "build_end_of_day",
]