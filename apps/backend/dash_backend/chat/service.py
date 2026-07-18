"""Conversation CRUD service.

Provides high-level operations for managing conversations and
their messages. All functions accept an async SQLAlchemy session
and return domain objects or raise appropriate exceptions.
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ScalarResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from dash_backend.db.models.conversation import Conversation
from dash_backend.db.models.conversation_summary import ConversationSummary
from dash_backend.db.models.message import Message, MessageRole


# ──────────────────────────────────────────────
# Conversations
# ──────────────────────────────────────────────


async def create_conversation(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    title: str | None = None,
    model: str | None = None,
) -> Conversation:
    """Create a new conversation for the given user."""
    conversation = Conversation(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        title=title or "New Chat",
        model=model,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def get_conversation(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    load_messages: bool = False,
) -> Conversation | None:
    """Get a single conversation by id, optionally with messages."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    query = select(Conversation).where(Conversation.id == cid)
    if load_messages:
        query = query.options(selectinload(Conversation.messages))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_user_conversations(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    include_archived: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Conversation], int]:
    """List conversations for a user, newest first.

    Returns (conversations, total_count). Archived conversations
    are excluded unless ``include_archived`` is True.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    filters = [Conversation.user_id == uid]
    if not include_archived:
        filters.append(Conversation.is_archived.is_(False))

    count_q = select(func.count(Conversation.id)).where(*filters)
    total = await session.scalar(count_q) or 0

    query = (
        select(Conversation)
        .where(*filters)
        .order_by(Conversation.is_pinned.desc(), Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total


async def search_conversations(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    query: str,
    *,
    limit: int = 20,
) -> list[Conversation]:
    """Search conversations by title (case-insensitive contains)."""
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    stmt = (
        select(Conversation)
        .where(
            Conversation.user_id == uid,
            Conversation.is_archived.is_(False),
            Conversation.title.ilike(f"%{query}%"),
        )
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_conversation(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    **kwargs: Any,
) -> Conversation | None:
    """Update conversation fields. Returns the updated conversation."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    # Build update dict from non-None kwargs
    allowed_fields = {"title", "is_pinned", "is_favorited", "is_archived", "summary", "model"}
    update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

    if not update_data:
        return await get_conversation(session, cid)

    if "is_archived" in update_data:
        update_data["archived_at"] = datetime.now(UTC) if update_data["is_archived"] else None

    stmt = update(Conversation).where(Conversation.id == cid).values(**update_data)
    await session.execute(stmt)
    await session.commit()
    return await get_conversation(session, cid)


async def archive_conversation(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
) -> Conversation | None:
    """Soft-delete a conversation by archiving it."""
    return await update_conversation(session, conversation_id, is_archived=True)


async def delete_conversation(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
) -> bool:
    """Permanently delete a conversation and all its messages."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    conv = await session.get(Conversation, cid)
    if conv is None:
        return False
    await session.delete(conv)
    await session.commit()
    return True


# ──────────────────────────────────────────────
# Messages
# ──────────────────────────────────────────────


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
    before_id: str | uuid.UUID | None = None,
) -> tuple[list[Message], int]:
    """Get messages for a conversation, oldest first (paginated).

    Supports cursor-based pagination via ``before_id``.
    Returns (messages, total_count).
    """
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    count_q = select(func.count(Message.id)).where(Message.conversation_id == cid)
    total = await session.scalar(count_q) or 0

    filters = [Message.conversation_id == cid]
    if before_id:
        bid = uuid.UUID(before_id) if isinstance(before_id, str) else before_id
        before_msg = await session.get(Message, bid)
        if before_msg:
            filters.append(Message.created_at < before_msg.created_at)

    query = (
        select(Message)
        .where(*filters)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    messages = list(result.scalars().all())
    messages.reverse()  # Return oldest first
    return messages, total


async def add_message(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    role: MessageRole,
    content: str,
    *,
    token_count: int | None = None,
    model: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Message:
    """Add a message to a conversation and update counters."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id

    message = Message(
        conversation_id=cid,
        role=role,
        content=content,
        token_count=token_count,
        model=model,
        meta=meta,
    )
    session.add(message)

    # Update conversation counters
    now = datetime.now(UTC)
    stmt = (
        update(Conversation)
        .where(Conversation.id == cid)
        .values(
            message_count=Conversation.message_count + 1,
            token_count=Conversation.token_count + (token_count or 0),
            last_message_at=now,
            model=model or Conversation.model,
        )
    )
    await session.execute(stmt)
    await session.commit()
    await session.refresh(message)
    return message


async def save_user_message(
    session: AsyncSession,
    conversation_id: str,
    content: str,
    **kwargs: Any,
) -> Message:
    """Convenience: add a user message."""
    return await add_message(session, conversation_id, MessageRole.USER, content, **kwargs)


async def save_assistant_message(
    session: AsyncSession,
    conversation_id: str,
    content: str,
    **kwargs: Any,
) -> Message:
    """Convenience: add an assistant message."""
    return await add_message(session, conversation_id, MessageRole.ASSISTANT, content, **kwargs)


# ──────────────────────────────────────────────
# Summaries
# ──────────────────────────────────────────────


AUTO_SUMMARIZE_THRESHOLD = 20  # messages


async def needs_summary(session: AsyncSession, conversation_id: str | uuid.UUID) -> bool:
    """Check if a conversation needs auto-summarization."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    conv = await session.get(Conversation, cid)
    if conv is None:
        return False
    return conv.message_count >= AUTO_SUMMARIZE_THRESHOLD


async def save_conversation_summary(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    summary: str,
    message_count: int,
    token_count: int,
) -> ConversationSummary:
    """Save a summary snapshot for a conversation."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    summary_entry = ConversationSummary(
        conversation_id=cid,
        summary=summary,
        message_count=message_count,
        token_count=token_count,
    )
    session.add(summary_entry)

    # Also update the conversation's inline summary
    stmt = (
        update(Conversation)
        .where(Conversation.id == cid)
        .values(summary=summary, summary_updated_at=datetime.now(UTC))
    )
    await session.execute(stmt)
    await session.commit()
    await session.refresh(summary_entry)
    return summary_entry


async def get_conversation_summaries(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    *,
    limit: int = 5,
) -> list[ConversationSummary]:
    """Get the most recent summaries for a conversation."""
    cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
    query = (
        select(ConversationSummary)
        .where(ConversationSummary.conversation_id == cid)
        .order_by(ConversationSummary.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all())