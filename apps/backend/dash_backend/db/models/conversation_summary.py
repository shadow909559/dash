"""ConversationSummary model.

Stores auto-generated summaries of conversations for long-term
context injection. When a conversation grows large, the system
summarizes it and stores the result here so it can be injected
into future prompts without loading the full history.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ConversationSummary(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A summary snapshot of a conversation at a point in time."""

    __tablename__ = "conversation_summaries"
    __table_args__ = (
        Index("ix_summaries_conversation_id", "conversation_id"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversation: Mapped["Conversation"] = relationship(back_populates="summaries")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<ConversationSummary id={self.id} conversation_id={self.conversation_id}>"