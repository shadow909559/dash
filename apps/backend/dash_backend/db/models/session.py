"""Session model.

Stores issued session/refresh tokens (as hashes, never raw values)
per user and, optionally, per device. Pure data structure only — no
issuance, validation, or auth logic lives here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Session(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An issued session tied to a user and, optionally, a device."""

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_id_expires_at", "user_id", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sessions")
    device: Mapped["Device | None"] = relationship(back_populates="sessions")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Session id={self.id} user_id={self.user_id}>"
