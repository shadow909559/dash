"""Persistent task state for complex-goal orchestration (decisions.md #90).

Schema and persistence follow the workflow-state conventions already used by
``services/workflow_builder.py``: a single JSON file under %LOCALAPPDATA%/DASH
(overridable via DASH_TASK_STATE), atomic tmp+os.replace writes, and
best-effort saves that never crash the caller. Tasks survive restarts; the
orchestrator resumes non-terminal tasks at boot.

The LLM never owns this state — it is written exclusively by the
orchestrator's deterministic control flow.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

STATE_VERSION = 1


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    WAITING_CONFIRMATION = "waiting_confirmation"
    RUNNING = "running"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    BLOCKED = "blocked"  # waiting on dependencies
    RUNNING = "running"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # dependency failed; honest cascade


class RiskLevel(str, Enum):
    SAFE = "safe"
    MODERATE = "moderate"
    HIGH = "high"


class VerificationStatus(str, Enum):
    NOT_RUN = "not_run"
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    FAILED = "failed"


@dataclass
class Verification:
    status: VerificationStatus = VerificationStatus.NOT_RUN
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value, "detail": self.detail[:400]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Verification":
        try:
            status = VerificationStatus(data.get("status", "not_run"))
        except ValueError:
            status = VerificationStatus.NOT_RUN
        return cls(status=status, detail=data.get("detail", ""))


@dataclass
class TaskStep:
    """One executable, verifiable step in a task graph."""

    id: str
    index: int
    description: str
    tool: str | None = None  # None → LLM tool selection at run time
    args: dict[str, Any] = field(default_factory=dict)
    purpose: str = ""
    risk: RiskLevel = RiskLevel.SAFE
    depends_on: list[str] = field(default_factory=list)
    # Declarative completion condition, e.g.
    #   {"type": "file_exists", "path": "..."}
    #   {"type": "output_contains", "expect": "passed"}
    #   {"type": "exit_code_zero"}
    #   {"type": "http_ok", "url": "http://127.0.0.1:8000/health"}
    #   {"type": "none"}  → honest NOT_VERIFIED when no check applies
    verify: dict[str, Any] | None = None
    status: StepStatus = StepStatus.PENDING
    attempts: int = 0
    max_attempts: int = 2
    result_summary: str | None = None
    error: str | None = None
    verification: Verification = field(default_factory=Verification)
    started_at: float = 0.0
    completed_at: float = 0.0
    # Open confirmation gate owned by THIS step (decisions.md #91): steps
    # gate independently so parallel waves never overwrite each other's
    # approval request. Cleared when the gate is approved/rejected/paused.
    confirmation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": self.index,
            "description": self.description,
            "tool": self.tool,
            "args": self.args,
            "purpose": self.purpose,
            "risk": self.risk.value,
            "depends_on": self.depends_on,
            "verify": self.verify,
            "status": self.status.value,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "result_summary": (self.result_summary or "")[:400] or None,
            "error": (self.error or "")[:400] or None,
            "verification": self.verification.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "confirmation": self.confirmation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TaskStep":
        try:
            risk = RiskLevel(data.get("risk", "safe"))
        except ValueError:
            risk = RiskLevel.SAFE
        try:
            status = StepStatus(data.get("status", "pending"))
        except ValueError:
            status = StepStatus.PENDING
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            index=int(data.get("index", 0)),
            description=data.get("description", ""),
            tool=data.get("tool"),
            args=data.get("args", {}) or {},
            purpose=data.get("purpose", ""),
            risk=risk,
            depends_on=[str(d) for d in data.get("depends_on", [])],
            verify=data.get("verify") if isinstance(data.get("verify"), dict) else None,
            status=status,
            attempts=int(data.get("attempts", 0)),
            max_attempts=int(data.get("max_attempts", 2)),
            result_summary=data.get("result_summary"),
            error=data.get("error"),
            verification=Verification.from_dict(data.get("verification", {})),
            started_at=float(data.get("started_at", 0.0)),
            completed_at=float(data.get("completed_at", 0.0)),
            confirmation=data.get("confirmation") if isinstance(data.get("confirmation"), dict) else None,
        )


@dataclass
class AgentTask:
    """A persistent complex task with its full execution history."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    goal: str = ""
    status: TaskStatus = TaskStatus.PENDING
    user_id: str | None = None
    steps: list[TaskStep] = field(default_factory=list)
    current_step_id: str | None = None
    max_retries: int = 2
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    # Pending confirmation snapshot (step id + what the user must approve)
    pending_confirmation: dict[str, Any] | None = None
    final_report: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)

    MAX_EVENTS = 200  # bounded so long tasks cannot grow the file forever

    def touch(self) -> None:
        self.updated_at = time.time()

    def record_event(self, event_type: str, detail: str) -> None:
        self.events.append({
            "ts": time.time(),
            "type": event_type,
            "detail": detail[:300],
        })
        if len(self.events) > self.MAX_EVENTS:
            self.events = self.events[-self.MAX_EVENTS:]

    @property
    def progress(self) -> dict[str, int]:
        done = sum(1 for s in self.steps if s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED))
        return {"completed": done, "total": len(self.steps)}

    def to_dict(self, include_events: bool = False) -> dict[str, Any]:
        data = {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "user_id": self.user_id,
            "steps": [s.to_dict() for s in self.steps],
            "current_step_id": self.current_step_id,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "pending_confirmation": self.pending_confirmation,
            "final_report": self.final_report,
            "progress": self.progress,
        }
        if include_events:
            data["events"] = self.events
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentTask":
        try:
            status = TaskStatus(data.get("status", "pending"))
        except ValueError:
            status = TaskStatus.PENDING
        return cls(
            id=data.get("id", str(uuid.uuid4())[:12]),
            goal=data.get("goal", ""),
            status=status,
            user_id=data.get("user_id"),
            steps=[TaskStep.from_dict(s) for s in data.get("steps", [])],
            current_step_id=data.get("current_step_id"),
            max_retries=int(data.get("max_retries", 2)),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            started_at=float(data.get("started_at", 0.0)),
            completed_at=float(data.get("completed_at", 0.0)),
            pending_confirmation=data.get("pending_confirmation"),
            final_report=data.get("final_report"),
            events=list(data.get("events", []))[-cls.MAX_EVENTS:],
        )


def default_state_path() -> Path:
    env = os.environ.get("DASH_TASK_STATE")
    if env:
        return Path(env)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DASH" / "task_state.json"


class TaskStateStore:
    """Atomic JSON persistence for AgentTasks (workflow-state conventions)."""

    def __init__(self, path: Path | None = None):
        self._path = Path(path) if path else default_state_path()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def load_all(self) -> dict[str, AgentTask]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Task state file unreadable: %s", self._path)
            return {}
        if raw.get("version") != STATE_VERSION:
            logger.warning("Task state version mismatch — starting empty")
            return {}
        tasks: dict[str, AgentTask] = {}
        for item in raw.get("tasks", []):
            try:
                task = AgentTask.from_dict(item)
            except Exception:
                logger.exception("Skipping corrupt task entry")
                continue
            tasks[task.id] = task
        return tasks

    def save_all(self, tasks: dict[str, AgentTask]) -> None:
        payload = {
            "version": STATE_VERSION,
            "saved_at": time.time(),
            "tasks": [t.to_dict(include_events=True) for t in tasks.values()],
        }
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError:
            logger.exception("Failed to persist task state to %s", self._path)

    def save_one(self, tasks: dict[str, AgentTask], task_id: str) -> None:
        """Persist a single task's current state (checkpoint)."""
        self.save_all(tasks)
