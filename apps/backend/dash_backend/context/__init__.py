"""DASH Context Engine (Phase 1).

Continuously assembles a representation of the user's digital environment:

- Device context  — CPU, RAM, disk, network, top processes, platform
- Project context — active git repository: branch, changed files, recent commits
- Activity context — recent goals/tasks and their status

The engine answers "Where am I?", "What am I working on?", and
"What changed since yesterday?" and emits a compact text block that is
dynamically injected into the LLM system prompt so DASH reasons with real
environment state instead of blind guesses.
"""

from dash_backend.context.engine import (
    EnvironmentContext,
    ContextEngine,
    get_context_engine,
    build_context_block,
)

__all__ = [
    "EnvironmentContext",
    "ContextEngine",
    "get_context_engine",
    "build_context_block",
]