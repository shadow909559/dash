"""Proactive Engine — observes system/user state and suggests helpful actions.

Examples:
- Low battery → suggest charger.
- Downloads folder messy → suggest cleanup.
- Unused large files → suggest removal.
- Long compile → suggest optimization.
- Meeting soon → suggest opening notes.

The engine is intentionally heuristic and low-risk: it only *suggests*, never
performs actions autonomously.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProactiveSuggestion:
    """A single proactive suggestion for the user."""

    title: str
    description: str
    category: str
    confidence: float
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "action": self.action,
            "payload": self.payload,
            "created_at": self.created_at,
        }


class ProactiveEngine:
    """Generates proactive suggestions from system and user state.

    All checks are best-effort and never raise. Suggestions are stored in an
    in-memory ring buffer and can be dismissed by the user.
    """

    def __init__(self, max_suggestions: int = 50) -> None:
        self._suggestions: List[ProactiveSuggestion] = []
        self._max_suggestions = max_suggestions
        self._dismissed: set[str] = set()

    # ── Generation ─────────────────────────────────────────────────────

    def generate(self, state: Optional[Dict[str, Any]] = None) -> List[ProactiveSuggestion]:
        """Generate suggestions from the current system/user state.

        ``state`` may include:
        - battery: {percent, plugged}
        - downloads: {file_count, total_mb}
        - large_files: [{path, size_mb}]
        - compile: {duration_s, project}
        - meeting: {title, starts_in_min}
        - disk: {percent}
        - memory: {percent}
        """
        state = state or {}
        suggestions: List[ProactiveSuggestion] = []

        # Battery
        battery = state.get("battery") or {}
        if isinstance(battery, dict):
            percent = battery.get("percent")
            plugged = battery.get("plugged", False)
            if isinstance(percent, (int, float)) and percent <= 20 and not plugged:
                suggestions.append(
                    ProactiveSuggestion(
                        title="Battery is low",
                        description=f"Battery is at {percent:.0f}%. Consider plugging in the charger.",
                        category="system",
                        confidence=0.9,
                        action="suggest_charger",
                        payload={"percent": percent},
                    )
                )

        # Downloads folder
        downloads = state.get("downloads") or {}
        if isinstance(downloads, dict):
            file_count = downloads.get("file_count", 0)
            total_mb = downloads.get("total_mb", 0)
            if file_count and file_count >= 20:
                suggestions.append(
                    ProactiveSuggestion(
                        title="Downloads folder is getting full",
                        description=f"{file_count} files ({total_mb:.0f} MB) in Downloads. Consider a cleanup.",
                        category="filesystem",
                        confidence=0.75,
                        action="suggest_cleanup",
                        payload={"file_count": file_count, "total_mb": total_mb},
                    )
                )

        # Large unused files
        large_files = state.get("large_files") or []
        if isinstance(large_files, list) and large_files:
            biggest = max(large_files, key=lambda f: f.get("size_mb", 0))
            if biggest.get("size_mb", 0) >= 500:
                suggestions.append(
                    ProactiveSuggestion(
                        title="Large file detected",
                        description=f"'{biggest.get('path', '')}' is {biggest.get('size_mb', 0):.0f} MB. Consider archiving or removing it.",
                        category="filesystem",
                        confidence=0.6,
                        action="suggest_removal",
                        payload=biggest,
                    )
                )

        # Long compile
        compile_info = state.get("compile") or {}
        if isinstance(compile_info, dict):
            duration_s = compile_info.get("duration_s", 0)
            if duration_s and duration_s >= 30:
                suggestions.append(
                    ProactiveSuggestion(
                        title="Compile is taking a while",
                        description=f"Compile took {duration_s:.0f}s for '{compile_info.get('project', '')}'. Consider incremental builds or caching.",
                        category="coding",
                        confidence=0.7,
                        action="suggest_optimization",
                        payload=compile_info,
                    )
                )

        # Meeting soon
        meeting = state.get("meeting") or {}
        if isinstance(meeting, dict):
            starts_in = meeting.get("starts_in_min")
            if isinstance(starts_in, (int, float)) and 0 <= starts_in <= 15:
                suggestions.append(
                    ProactiveSuggestion(
                        title="Meeting soon",
                        description=f"'{meeting.get('title', 'Meeting')}' starts in {starts_in:.0f} minutes. Open your notes?",
                        category="calendar",
                        confidence=0.85,
                        action="suggest_open_notes",
                        payload=meeting,
                    )
                )

        # Disk / memory pressure
        disk = state.get("disk") or {}
        if isinstance(disk, dict) and disk.get("percent", 0) >= 90:
            suggestions.append(
                ProactiveSuggestion(
                    title="Disk space is low",
                    description=f"Disk is {disk.get('percent', 0):.0f}% full. Consider freeing space.",
                    category="system",
                    confidence=0.8,
                    action="suggest_disk_cleanup",
                    payload=disk,
                )
            )

        memory = state.get("memory") or {}
        if isinstance(memory, dict) and memory.get("percent", 0) >= 90:
            suggestions.append(
                ProactiveSuggestion(
                    title="Memory pressure is high",
                    description=f"Memory usage is {memory.get('percent', 0):.0f}%. Consider closing unused applications.",
                    category="system",
                    confidence=0.8,
                    action="suggest_close_apps",
                    payload=memory,
                )
            )

        # Store new suggestions (dedupe by title).
        for s in suggestions:
            if s.title not in self._dismissed and not any(
                existing.title == s.title for existing in self._suggestions
            ):
                self._suggestions.append(s)

        # Rotate.
        if len(self._suggestions) > self._max_suggestions:
            self._suggestions = self._suggestions[-self._max_suggestions:]

        return suggestions

    # ── Accessors ──────────────────────────────────────────────────────

    def get(self, limit: int = 10) -> List[ProactiveSuggestion]:
        """Return the most recent suggestions."""
        return self._suggestions[-limit:]

    def dismiss(self, title: str) -> bool:
        """Dismiss a suggestion by title so it is not re-offered."""
        before = len(self._suggestions)
        self._suggestions = [s for s in self._suggestions if s.title != title]
        self._dismissed.add(title)
        return len(self._suggestions) < before

    def clear(self) -> None:
        """Clear all suggestions."""
        self._suggestions.clear()


# Global singleton
_proactive_engine: Optional[ProactiveEngine] = None


def get_proactive_engine() -> ProactiveEngine:
    """Return the global ProactiveEngine singleton."""
    global _proactive_engine
    if _proactive_engine is None:
        _proactive_engine = ProactiveEngine()
    return _proactive_engine