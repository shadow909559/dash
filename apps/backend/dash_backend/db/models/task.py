"""Task model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TaskStatus(str, enum.Enum):
    """Lifecycle status of a `Task`."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A unit of work DASH is tracking or automating for a user."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_user_id_status", "user_id", "status"),
        Index("ix_tasks_user_id_due_at", "user_id", "due_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", native_enum=False, length=16),
        default=TaskStatus.PENDING,
        nullable=False,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="tasks")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Task id={self.id} user_id={self.user_id} status={self.status}>"
