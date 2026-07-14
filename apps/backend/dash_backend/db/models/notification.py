"""Notification model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class NotificationType(str, enum.Enum):
    """Category of a `Notification`, used for client-side display."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    TASK = "task"
    SYSTEM = "system"


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A notification delivered (or to be delivered) to a user."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id_read_at", "user_id", "read_at"),
        Index("ix_notifications_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type", native_enum=False, length=16),
        default=NotificationType.INFO,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="notifications")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Notification id={self.id} user_id={self.user_id} type={self.type}>"
