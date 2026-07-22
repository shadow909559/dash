"""Memory model.

Backs the "long-term memory" feature described in the project
context: durable facts/snippets DASH can recall outside the scope of
a single conversation.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Index, String, Text, JSON, DateTime, func, Integer


from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import UUIDPrimaryKeyMixin


class Memory(UUIDPrimaryKeyMixin, Base):
    """A durable memory item belonging to a user."""


    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_user_id_type_created_at", "user_id", "type", "created_at"),
        Index("ix_memories_user_id_importance_last_accessed", "user_id", "importance", "last_accessed"),
        Index("ix_memories_user_id_last_accessed", "user_id", "last_accessed"),
        Index("ix_memories_user_id_access_count", "user_id", "access_count"),
    )


    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Memory phase-1 schema
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 0.0 - 1.0 where higher means more important
    importance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    tags: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Access tracking (used by ranking)
    last_accessed: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Legacy compatibility
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Stored embedding vector (future RAG retrieval milestone).
    embedding: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)  # store embedding as JSON for SQLite compatibility

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


    user: Mapped["User"] = relationship(back_populates="memories")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Memory id={self.id} user_id={self.user_id}>"

