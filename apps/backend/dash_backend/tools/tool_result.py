"""Tool result data model.

Encapsulates the outcome of a tool execution, including status,
output data, error details, and timing information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ToolStatus(str, Enum):
    """Execution status of a tool."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PENDING_CONFIRMATION = "pending_confirmation"
    REJECTED = "rejected"


class ToolEvent(str, Enum):
    """Lifecycle events emitted during tool execution."""

    STARTED = "tool.started"
    PROGRESS = "tool.progress"
    FINISHED = "tool.finished"
    ERROR = "tool.error"
    CONFIRMATION_REQUIRED = "tool.confirmation_required"
    CONFIRMED = "tool.confirmed"
    REJECTED = "tool.rejected"


@dataclass
class ToolResult:
    """Result of a single tool execution.

    Attributes:
        tool_name:       Name of the tool that was executed.
        status:          Execution status.
        output:          Structured output data (tool-specific).
        summary:         Human-readable summary of the result.
        error_message:   Error details if status == ERROR.
        started_at:      When execution began (UTC).
        finished_at:     When execution finished (UTC).
        duration_ms:     Execution duration in milliseconds.
        raw_output:      Raw stdout/stderr if applicable.
        confirmation_token: Token if pending user confirmation.
        meta:            Extra metadata about execution.
    """

    tool_name: str
    status: ToolStatus = ToolStatus.SUCCESS
    output: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: float = 0.0
    raw_output: str = ""
    confirmation_token: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.started_at is None:
            self.started_at = datetime.now(timezone.utc)
        if self.finished_at is None:
            self.finished_at = datetime.now(timezone.utc)
        if not self.duration_ms and self.started_at and self.finished_at:
            delta = self.finished_at - self.started_at
            self.duration_ms = delta.total_seconds() * 1000.0

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.status in (ToolStatus.ERROR, ToolStatus.TIMEOUT)

    @property
    def is_pending_confirmation(self) -> bool:
        return self.status == ToolStatus.PENDING_CONFIRMATION

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "tool_name": self.tool_name,
            "status": self.status.value,
            "output": self.output,
            "summary": self.summary,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": round(self.duration_ms, 2),
            "raw_output": self.raw_output,
            "confirmation_token": self.confirmation_token,
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolResult:
        """Reconstruct a ToolResult from :meth:`to_dict` output.

        Used to reuse an already-executed result (e.g. from the streaming
        executor) without running the tool a second time.
        """
        status_raw = data.get("status", ToolStatus.SUCCESS.value)
        try:
            tool_status = ToolStatus(status_raw)
        except ValueError:
            tool_status = ToolStatus.ERROR
        started_raw = data.get("started_at")
        finished_raw = data.get("finished_at")
        return cls(
            tool_name=data.get("tool_name", ""),
            status=tool_status,
            output=data.get("output") or {},
            summary=data.get("summary", ""),
            error_message=data.get("error_message", ""),
            started_at=datetime.fromisoformat(started_raw) if started_raw else None,
            finished_at=datetime.fromisoformat(finished_raw) if finished_raw else None,
            duration_ms=float(data.get("duration_ms") or 0.0),
            raw_output=data.get("raw_output", ""),
            confirmation_token=data.get("confirmation_token"),
            meta=data.get("meta") or {},
        )