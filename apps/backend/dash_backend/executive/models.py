from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, String, Text, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from dash_backend.db.base import Base
from dash_backend.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class GoalStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Goal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=GoalStatus.PENDING)
    meta_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "executive_tasks"

    goal_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=TaskStatus.PENDING)
    attempt: Mapped[int] = mapped_column(default=0)
    meta_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    # Worker claim fields for durable execution across processes
    claimed_by: Mapped[Optional[uuid.UUID]] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(nullable=True)


class ExecutionHistory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "execution_history"

    task_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[float]] = mapped_column(nullable=True)
    success: Mapped[Optional[bool]] = mapped_column(nullable=True)


class Approval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "approvals"

    confirmation_token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    meta_data: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    resolved: Mapped[bool] = mapped_column(nullable=False, default=False)
