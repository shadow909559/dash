"""Message model."""

from __future__ import annotations

import enum
import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class MessageRole(str, enum.Enum):
    """Who authored a message within a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single message within a `Conversation`."""

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", native_enum=False, length=16),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"<Message id={self.id} conversation_id={self.conversation_id} role={self.role}>"
