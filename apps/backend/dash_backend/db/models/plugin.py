"""Plugin model.

Backs the "plugin system" feature described in the project context:
a plugin installed (and configured) for a given user.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Plugin(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A plugin installed for a user.

    Uniqueness is scoped per-user (`user_id` + `name`) so the same
    plugin name can be installed independently by different users.
    """

    __tablename__ = "plugins"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_plugins_user_id_name"),
        Index("ix_plugins_user_id_enabled", "user_id", "enabled"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="plugins")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Plugin id={self.id} user_id={self.user_id} name={self.name!r}>"
