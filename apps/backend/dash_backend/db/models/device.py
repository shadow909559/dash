"""Device model.

Represents a client the user connects from or that DASH acts on
behalf of: a mobile app install, a desktop agent, or a browser.
Matches the architecture in the project context (Android App ->
FastAPI Backend -> Desktop Agent).
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import List

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class DeviceType(str, enum.Enum):
    """What kind of client a `Device` row represents."""

    DESKTOP_AGENT = "desktop_agent"
    MOBILE = "mobile"
    BROWSER = "browser"
    OTHER = "other"


class Device(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A device/client registered to a user."""

    __tablename__ = "devices"
    __table_args__ = (
        Index("ix_devices_user_id_type", "user_id", "type"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[DeviceType] = mapped_column(
        Enum(DeviceType, name="device_type", native_enum=False, length=16),
        nullable=False,
    )
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="devices")
    sessions: Mapped[List["Session"]] = relationship(back_populates="device")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Device id={self.id} user_id={self.user_id} type={self.type}>"
