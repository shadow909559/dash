"""Device model.

This is a data model only (no endpoints).

Implements SQLAlchemy 2 ORM mapping for registered client devices.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from dash_backend.db.base import Base


class Device(Base):
    """Registered device associated with a user."""

    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
    )

    device_name: Mapped[str] = mapped_column(String(128), nullable=False)
    device_type: Mapped[str] = mapped_column(String(64), nullable=False)
    os: Mapped[str] = mapped_column(String(64), nullable=False)

    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    trusted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = ()

