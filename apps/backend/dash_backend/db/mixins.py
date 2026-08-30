"""Shared mixins for ORM models.

Every model uses a UUID primary key and `created_at` / `updated_at`
timestamps, so both are factored out here rather than repeated on
each model.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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

    Timezone-aware, generated application-side. This is deliberate: with
    server-side defaults (func.now()), SQLAlchemy expires these columns
    after INSERT/UPDATE to refetch server values — any later serialization
    outside a greenlet context then explodes with MissingGreenlet. Python
    defaults keep values loaded on the instance at all times.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
        nullable=False,
    )
