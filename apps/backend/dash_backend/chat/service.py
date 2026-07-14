from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.conversation import Conversation
from dash_backend.db.models.message import Message, MessageRole


async def get_or_create_conversation(
    session: AsyncSession,
    user_id: str,
    conversation_id: str | None = None,
) -> Conversation:
    if conversation_id:
        conversation = await session.get(
            Conversation,
            uuid.UUID(conversation_id),
        )

        if conversation:
            return conversation

    conversation = Conversation(
        user_id=uuid.UUID(user_id),
        title="New Chat",
    )

    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)

    return conversation


async def save_message(
    session: AsyncSession,
    conversation_id: str,
    role: MessageRole,
    content: str,
):
    message = Message(
        conversation_id=uuid.UUID(conversation_id),
        role=role,
        content=content,
    )

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message


async def get_conversation_messages(
    session: AsyncSession,
    conversation_id: str,
):
    result = await session.execute(
        select(Message)
        .where(
            Message.conversation_id == uuid.UUID(conversation_id)
        )
        .order_by(Message.created_at)
    )

    return result.scalars().all()


async def save_user_message(
    session: AsyncSession,
    conversation_id: str,
    content: str,
):
    return await save_message(
        session,
        conversation_id,
        MessageRole.USER,
        content,
    )


async def save_assistant_message(
    session: AsyncSession,
    conversation_id: str,
    content: str,
):
    return await save_message(
        session,
        conversation_id,
        MessageRole.ASSISTANT,
        content,
    )