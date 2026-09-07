"""Context Engine — automatically gathers relevant context before answering.

Tracks:
- What the user is doing (current task)
- Which project is open
- Current repository
- Recent files
- Recent searches
- Recent conversations
- Current coding language
- Current browser tabs
- Current desktop state

The engine maintains a per-user context snapshot that the pipeline injects
into every request so DASH never asks questions it can infer.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_CONTEXT = "context"
SOURCE_NEURAL_CONTEXT = "neural_context"

# Maximum entries kept per context bucket.
_MAX_RECENT_FILES = 20
_MAX_RECENT_SEARCHES = 20
_MAX_RECENT_CONVERSATIONS = 20
_MAX_BROWSER_TABS = 20


@dataclass
class ContextSnapshot:
    """The current context snapshot for a user."""

    current_task: str = ""
    current_project: str = ""
    current_repository: str = ""
    current_language: str = ""
    current_folder: str = ""
    recent_files: List[str] = field(default_factory=list)
    recent_searches: List[str] = field(default_factory=list)
    recent_conversations: List[str] = field(default_factory=list)
    browser_tabs: List[str] = field(default_factory=list)
    desktop_state: Dict[str, Any] = field(default_factory=dict)
    running_services: List[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_task": self.current_task,
            "current_project": self.current_project,
            "current_repository": self.current_repository,
            "current_language": self.current_language,
            "current_folder": self.current_folder,
            "recent_files": self.recent_files,
            "recent_searches": self.recent_searches,
            "recent_conversations": self.recent_conversations,
            "browser_tabs": self.browser_tabs,
            "desktop_state": self.desktop_state,
            "running_services": self.running_services,
            "updated_at": self.updated_at,
        }


class ContextEngine:
    """Maintains a per-user context snapshot for automatic context gathering."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, ContextSnapshot] = {}

    # ── Updates ────────────────────────────────────────────────────────

    def update(
        self,
        user_id: str,
        **kwargs: Any,
    ) -> ContextSnapshot:
        """Update one or more context fields for a user."""
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        for key, value in kwargs.items():
            if value is None:
                continue
            if hasattr(snapshot, key):
                setattr(snapshot, key, value)
        snapshot.updated_at = time.time()
        return snapshot

    def set_current_task(self, user_id: str, task: str) -> None:
        self.update(user_id, current_task=task)

    def set_project(self, user_id: str, project: str, repository: str = "") -> None:
        self.update(user_id, current_project=project, current_repository=repository)

    def set_language(self, user_id: str, language: str) -> None:
        self.update(user_id, current_language=language)

    def set_folder(self, user_id: str, folder: str) -> None:
        self.update(user_id, current_folder=folder)

    def add_recent_file(self, user_id: str, path: str) -> None:
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        if path not in snapshot.recent_files:
            snapshot.recent_files.insert(0, path)
            snapshot.recent_files = snapshot.recent_files[:_MAX_RECENT_FILES]
        snapshot.updated_at = time.time()

    def add_recent_search(self, user_id: str, query: str) -> None:
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        if query not in snapshot.recent_searches:
            snapshot.recent_searches.insert(0, query)
            snapshot.recent_searches = snapshot.recent_searches[:_MAX_RECENT_SEARCHES]
        snapshot.updated_at = time.time()

    def add_recent_conversation(self, user_id: str, topic: str) -> None:
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        if topic not in snapshot.recent_conversations:
            snapshot.recent_conversations.insert(0, topic)
            snapshot.recent_conversations = snapshot.recent_conversations[:_MAX_RECENT_CONVERSATIONS]
        snapshot.updated_at = time.time()

    def set_browser_tabs(self, user_id: str, tabs: List[str]) -> None:
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        snapshot.browser_tabs = list(tabs)[:_MAX_BROWSER_TABS]
        snapshot.updated_at = time.time()

    def set_desktop_state(self, user_id: str, state: Dict[str, Any]) -> None:
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        snapshot.desktop_state = state or {}
        snapshot.updated_at = time.time()

    def set_running_services(self, user_id: str, services: List[str]) -> None:
        snapshot = self._snapshots.setdefault(user_id, ContextSnapshot())
        snapshot.running_services = list(services)
        snapshot.updated_at = time.time()

    # ── Accessors ──────────────────────────────────────────────────────

    def get_snapshot(self, user_id: str) -> ContextSnapshot:
        """Return the current context snapshot for a user."""
        return self._snapshots.setdefault(user_id, ContextSnapshot())

    def build_context_string(self, user_id: str) -> str:
        """Build a compact context string for prompt injection."""
        snap = self.get_snapshot(user_id)
        parts: List[str] = []

        if snap.current_task:
            parts.append(f"Current task: {snap.current_task}")
        if snap.current_project:
            parts.append(f"Project: {snap.current_project}")
        if snap.current_repository:
            parts.append(f"Repository: {snap.current_repository}")
        if snap.current_language:
            parts.append(f"Language: {snap.current_language}")
        if snap.current_folder:
            parts.append(f"Folder: {snap.current_folder}")
        if snap.recent_files:
            parts.append(f"Recent files: {', '.join(snap.recent_files[:5])}")
        if snap.recent_searches:
            parts.append(f"Recent searches: {', '.join(snap.recent_searches[:3])}")
        if snap.recent_conversations:
            parts.append(f"Recent topics: {', '.join(snap.recent_conversations[:3])}")
        if snap.browser_tabs:
            parts.append(f"Browser tabs: {', '.join(snap.browser_tabs[:5])}")
        if snap.running_services:
            parts.append(f"Running services: {', '.join(snap.running_services[:5])}")

        return "\n".join(parts)

    # ── Persistence ────────────────────────────────────────────────────

    async def persist_snapshot(self, session: Any, user_id: str) -> None:
        """Persist the context snapshot as a memory."""
        try:
            from dash_backend.memory import service as memory_service

            snap = self.get_snapshot(user_id)
            await memory_service.save_memory(
                session,
                user_id,
                json.dumps(snap.to_dict(), default=str),
                source=SOURCE_NEURAL_CONTEXT,
                category=CATEGORY_CONTEXT,
                importance=0.65,
                memory_type="Summary",
                title="Context snapshot",
            )
        except Exception:
            logger.exception("Failed to persist context snapshot")


# Global singleton
_context_engine: Optional[ContextEngine] = None


def get_context_engine() -> ContextEngine:
    """Return the global ContextEngine singleton."""
    global _context_engine
    if _context_engine is None:
        _context_engine = ContextEngine()
    return _context_engine