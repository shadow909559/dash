"""Automation ORM model."""

from __future__ import annotations

import uuid
from typing import Any
from datetime import datetime

from sqlalchemy import JSON, Index, String, Text, Boolean, ForeignKey, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class Automation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents a scheduled automation owned by a user."""

    __tablename__ = "automations"
    __table_args__ = (
        Index("ix_automations_user_id_enabled", "user_id", "enabled"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Triggering configuration
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    schedule: Mapped[str] = mapped_column(String(256), nullable=False)

    # Tool to execute and JSON arguments
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_arguments: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationship to user follows project style
    user = relationship("User", back_populates="automations", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Automation id={self.id} name={self.name} user_id={self.user_id}>" 


class AutomationExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Record of an automation run."""

    __tablename__ = "automation_executions"
    __table_args__ = (
        Index("ix_execution_automation_id_created_at", "automation_id", "created_at"),
    )

    automation_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("automations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps from tool execution (optional, may be None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AutomationExecution id={self.id} automation_id={self.automation_id} status={self.status}>" 
