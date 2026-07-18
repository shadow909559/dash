"""Conversation model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A conversation thread between a user and DASH.

    Groups an ordered sequence of `Message` rows.
    Supports pinning, favoriting, archiving, and auto-summarization.
    """

    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_user_id_created_at", "user_id", "created_at"),
        Index("ix_conversations_user_id_pinned", "user_id", "is_pinned"),
        Index("ix_conversations_user_id_archived", "user_id", "is_archived"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_favorited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(default=0, nullable=False)
    token_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    summaries: Mapped[List["ConversationSummary"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationSummary.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Conversation id={self.id} user_id={self.user_id} title={self.title!r}>"