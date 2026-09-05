"""Command pipeline data models.

Every command flowing through the pipeline has:
  - command_id: unique identifier
  - status: lifecycle status
  - started_at / completed_at: timing
  - error: optional error details
  - result: output payload
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CommandStatus(str, Enum):
    """Lifecycle status of a remote command."""
    PENDING = "pending"
    QUEUED = "queued"
    APPROVED = "approved"
    REJECTED = "rejected"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class CommandCategory(str, Enum):
    """Category for grouping and permission scope."""
    SYSTEM = "system"
    FILES = "files"
    APPS = "apps"
    TERMINAL = "terminal"
    BROWSER = "browser"
    CLIPBOARD = "clipboard"
    NOTIFICATIONS = "notifications"
    VOICE = "voice"
    AUTOMATION = "automation"
    WINDOW = "window"
    MOUSE = "mouse"
    KEYBOARD = "keyboard"


class CommandPriority(int, Enum):
    """Priority for command queue ordering."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class PermissionDecision(str, Enum):
    """User's permission decision."""
    ALLOW_ONCE = "allow_once"
    ALWAYS_ALLOW = "always_allow"
    DENY = "deny"
    DENY_FOREVER = "deny_forever"


class CommandRequest(BaseModel):
    """A command to execute on the desktop."""

    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: CommandCategory = CommandCategory.SYSTEM
    action: str  # e.g. "shutdown", "open_url", "copy_text"
    params: dict[str, Any] = Field(default_factory=dict)
    priority: CommandPriority = CommandPriority.NORMAL
    source: str = "android"  # "android", "desktop", "automation", "voice"
    source_client_id: str | None = None
    user_id: str | None = None
    requires_approval: bool = True
    allow_always: bool = False
    timeout_seconds: float = 30.0
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class CommandResult(BaseModel):
    """The structured result of a command execution."""

    command_id: str
    status: CommandStatus = CommandStatus.PENDING
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    duration_ms: float = 0.0

    model_config = {"use_enum_values": True}


class ApprovalRequest(BaseModel):
    """Sent to desktop for user permission decision."""

    command_id: str
    category: CommandCategory
    action: str
    params: dict[str, Any]
    description: str
    source: str
    created_at: str


class ApprovalResponse(BaseModel):
    """User's decision on an approval request."""

    command_id: str
    decision: PermissionDecision
    responded_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
