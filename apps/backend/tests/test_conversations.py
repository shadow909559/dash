"""Tests for conversation CRUD operations."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.chat.service import (
    add_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    get_conversation_messages,
    get_user_conversations,
    search_conversations,
    update_conversation,
)
from dash_backend.db.models.conversation import Conversation
from dash_backend.db.models.message import MessageRole


pytestmark = pytest.mark.asyncio


async def test_create_conversation(db_session: AsyncSession, test_user_id: str) -> None:
    """Test creating a new conversation."""
    conv = await create_conversation(db_session, test_user_id, title="Test Chat")
    assert conv is not None
    assert conv.title == "Test Chat"
    assert conv.user_id == uuid.UUID(test_user_id)
    assert conv.is_pinned is False
    assert conv.is_archived is False
    assert conv.message_count == 0


async def test_get_conversation(db_session: AsyncSession, test_user_id: str) -> None:
    """Test retrieving a conversation by id."""
    conv = await create_conversation(db_session, test_user_id)
    retrieved = await get_conversation(db_session, conv.id)
    assert retrieved is not None
    assert retrieved.id == conv.id


async def test_get_user_conversations(db_session: AsyncSession, test_user_id: str) -> None:
    """Test listing conversations for a user."""
    await create_conversation(db_session, test_user_id, title="Chat 1")
    await create_conversation(db_session, test_user_id, title="Chat 2")

    conversations, total = await get_user_conversations(db_session, test_user_id)
    assert total >= 2
    assert len(conversations) >= 2


async def test_search_conversations(db_session: AsyncSession, test_user_id: str) -> None:
    """Test searching conversations by title."""
    await create_conversation(db_session, test_user_id, title="Python Project")
    await create_conversation(db_session, test_user_id, title="Flutter App")

    results = await search_conversations(db_session, test_user_id, "Python")
    assert len(results) >= 1
    assert "Python" in results[0].title


async def test_update_conversation(db_session: AsyncSession, test_user_id: str) -> None:
    """Test updating conversation metadata."""
    conv = await create_conversation(db_session, test_user_id)
    updated = await update_conversation(db_session, conv.id, title="Renamed", is_pinned=True)
    assert updated is not None
    assert updated.title == "Renamed"
    assert updated.is_pinned is True


async def test_delete_conversation(db_session: AsyncSession, test_user_id: str) -> None:
    """Test deleting a conversation."""
    conv = await create_conversation(db_session, test_user_id)
    deleted = await delete_conversation(db_session, conv.id)
    assert deleted is True

    retrieved = await get_conversation(db_session, conv.id)
    assert retrieved is None


async def test_add_and_get_messages(db_session: AsyncSession, test_user_id: str) -> None:
    """Test adding messages and retrieving them."""
    conv = await create_conversation(db_session, test_user_id)

    msg1 = await add_message(
        db_session, conv.id, MessageRole.USER, "Hello", token_count=5
    )
    msg2 = await add_message(
        db_session, conv.id, MessageRole.ASSISTANT, "Hi there!", token_count=10
    )

    messages, total = await get_conversation_messages(db_session, conv.id)
    assert total == 2
    assert len(messages) == 2
    assert messages[0].content == "Hello"
    assert messages[1].content == "Hi there!"

    # Verify conversation counters were updated
    conv = await get_conversation(db_session, conv.id)
    assert conv is not None
    assert conv.message_count == 2
    assert conv.token_count == 15