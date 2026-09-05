"""Continuity Engine — restores state after DASH restarts.

If DASH restarts, it restores:
- Conversation
- Open tasks
- Running workflows
- Agent state
- Desktop state
- Orb state
- Voice state

The engine snapshots state periodically and restores it on startup so the AI
continues as if nothing happened.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_CONTINUITY = "continuity"
SOURCE_NEURAL_CONTINUITY = "neural_continuity"


@dataclass
class ContinuityState:
    """A snapshot of DASH state for restoration after restart."""

    conversation_topic: str = ""
    open_tasks: List[Dict[str, Any]] = field(default_factory=list)
    running_workflows: List[Dict[str, Any]] = field(default_factory=list)
    agent_state: Dict[str, Any] = field(default_factory=dict)
    desktop_state: Dict[str, Any] = field(default_factory=dict)
    orb_state: Dict[str, Any] = field(default_factory=dict)
    voice_state: Dict[str, Any] = field(default_factory=dict)
    last_active: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_topic": self.conversation_topic,
            "open_tasks": self.open_tasks,
            "running_workflows": self.running_workflows,
            "agent_state": self.agent_state,
            "desktop_state": self.desktop_state,
            "orb_state": self.orb_state,
            "voice_state": self.voice_state,
            "last_active": self.last_active,
        }


class ContinuityEngine:
    """Snapshots and restores DASH state across restarts."""

    def __init__(self) -> None:
        self._states: Dict[str, ContinuityState] = {}

    # ── Snapshot ───────────────────────────────────────────────────────

    def snapshot(
        self,
        user_id: str,
        **kwargs: Any,
    ) -> ContinuityState:
        """Update and store a continuity snapshot for a user."""
        state = self._states.setdefault(user_id, ContinuityState())
        for key, value in kwargs.items():
            if value is None:
                continue
            if hasattr(state, key):
                setattr(state, key, value)
        state.last_active = time.time()
        return state

    def add_open_task(self, user_id: str, task: Dict[str, Any]) -> None:
        state = self._states.setdefault(user_id, ContinuityState())
        task_id = task.get("id") or task.get("name") or str(len(state.open_tasks))
        # Replace if exists, else append.
        for i, existing in enumerate(state.open_tasks):
            if (existing.get("id") or existing.get("name")) == task_id:
                state.open_tasks[i] = task
                break
        else:
            state.open_tasks.append(task)
        state.last_active = time.time()

    def remove_open_task(self, user_id: str, task_id: str) -> bool:
        state = self._states.setdefault(user_id, ContinuityState())
        before = len(state.open_tasks)
        state.open_tasks = [t for t in state.open_tasks if (t.get("id") or t.get("name")) != task_id]
        return len(state.open_tasks) < before

    def add_workflow(self, user_id: str, workflow: Dict[str, Any]) -> None:
        state = self._states.setdefault(user_id, ContinuityState())
        state.running_workflows.append(workflow)
        state.last_active = time.time()

    def complete_workflow(self, user_id: str, workflow_id: str) -> bool:
        state = self._states.setdefault(user_id, ContinuityState())
        before = len(state.running_workflows)
        state.running_workflows = [
            w for w in state.running_workflows if w.get("id") != workflow_id
        ]
        return len(state.running_workflows) < before

    # ── Restore ────────────────────────────────────────────────────────

    def get_state(self, user_id: str) -> ContinuityState:
        """Return the current continuity state for a user."""
        return self._states.setdefault(user_id, ContinuityState())

    def restore(self, user_id: str) -> ContinuityState:
        """Restore the last known state for a user.

        Returns the state so the pipeline can resume conversations, tasks,
        workflows, and agent/desktop/orb/voice state.
        """
        state = self.get_state(user_id)
        logger.info(
            "Restored continuity for user %s: %d tasks, %d workflows",
            user_id,
            len(state.open_tasks),
            len(state.running_workflows),
        )
        return state

    def has_state(self, user_id: str) -> bool:
        """Whether a user has any continuity state to restore."""
        state = self._states.get(user_id)
        if state is None:
            return False
        return bool(
            state.conversation_topic
            or state.open_tasks
            or state.running_workflows
            or state.agent_state
            or state.desktop_state
            or state.orb_state
            or state.voice_state
        )

    # ── Persistence ────────────────────────────────────────────────────

    async def persist_state(self, session: Any, user_id: str) -> None:
        """Persist the continuity snapshot as a memory."""
        try:
            from dash_backend.memory import service as memory_service

            state = self.get_state(user_id)
            await memory_service.save_memory(
                session,
                user_id,
                json.dumps(state.to_dict(), default=str),
                source=SOURCE_NEURAL_CONTINUITY,
                category=CATEGORY_CONTINUITY,
                importance=0.8,
                memory_type="Summary",
                title="Continuity snapshot",
            )
        except Exception:
            logger.exception("Failed to persist continuity state")

    async def load_state(self, session: Any, user_id: str) -> bool:
        """Load the last persisted continuity state from memory."""
        try:
            from dash_backend.memory import service as memory_service

            memories, _ = await memory_service.get_user_memories(
                session,
                user_id,
                limit=5,
                category=CATEGORY_CONTINUITY,
            )
            for m in memories:
                if m.source != SOURCE_NEURAL_CONTINUITY:
                    continue
                try:
                    data = json.loads(m.content)
                    state = self._states.setdefault(user_id, ContinuityState())
                    for key, value in data.items():
                        if hasattr(state, key):
                            setattr(state, key, value)
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            logger.exception("Failed to load continuity state")
            return False


# Global singleton
_continuity_engine: Optional[ContinuityEngine] = None


def get_continuity_engine() -> ContinuityEngine:
    """Return the global ContinuityEngine singleton."""
    global _continuity_engine
    if _continuity_engine is None:
        _continuity_engine = ContinuityEngine()
    return _continuity_engine