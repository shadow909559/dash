"""Memory model.

Backs the "long-term memory" feature described in the project
context: durable facts/snippets DASH can recall outside the scope of
a single conversation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Memory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A durable memory item belonging to a user."""

    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_user_id_created_at", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # User-defined category for filtering memories.
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    importance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Stored embedding vector (future RAG retrieval milestone).
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(Float), nullable=True)

    user: Mapped["User"] = relationship(back_populates="memories")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Memory id={self.id} user_id={self.user_id}>"

