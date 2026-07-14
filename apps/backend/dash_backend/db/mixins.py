"""Shared mixins for ORM models.

Every model uses a UUID primary key and `created_at` / `updated_at`
timestamps, so both are factored out here rather than repeated on
each model.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column named `id`.

    The UUID is generated application-side (Python `uuid.uuid4`) so
    it is available before the row is flushed to the database and no
    Postgres extension (e.g. pgcrypto) is required.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Adds `created_at` / `updated_at` timestamp columns.

    Both are timezone-aware and set by the database server
    (`func.now()`) so they are consistent regardless of which
    application server or timezone writes the row.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
