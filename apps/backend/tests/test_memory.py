"""Tests for memory service operations."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.memory.service import (
    build_memory_context,
    clear_user_memories,
    delete_memory,
    get_user_memories,
    retrieve_memory,
    save_memory,
    summarize_conversation,
    update_memory,
)


pytestmark = pytest.mark.asyncio


async def test_save_memory(db_session: AsyncSession, test_user_id: str) -> None:
    """Test saving a new memory."""
    memory = await save_memory(
        db_session, test_user_id, "User likes Python", source="conversation", importance=0.8
    )
    assert memory is not None
    assert memory.content == "User likes Python"
    assert memory.source == "conversation"
    assert memory.importance == 0.8
    assert memory.user_id == uuid.UUID(test_user_id)


async def test_retrieve_memory(db_session: AsyncSession, test_user_id: str) -> None:
    """Test retrieving a memory by id."""
    memory = await save_memory(db_session, test_user_id, "Test memory")
    retrieved = await retrieve_memory(db_session, memory.id)
    assert retrieved is not None
    assert retrieved.id == memory.id
    assert retrieved.content == "Test memory"


async def test_get_user_memories(db_session: AsyncSession, test_user_id: str) -> None:
    """Test listing memories for a user."""
    await save_memory(db_session, test_user_id, "Memory 1", importance=0.5)
    await save_memory(db_session, test_user_id, "Memory 2", importance=0.9)

    memories, total = await get_user_memories(db_session, test_user_id)
    assert total >= 2
    assert len(memories) >= 2
    # Should be ordered by importance descending
    assert memories[0].importance >= memories[-1].importance


async def test_get_user_memories_min_importance(
    db_session: AsyncSession, test_user_id: str
) -> None:
    """Test filtering memories by minimum importance."""
    await save_memory(db_session, test_user_id, "Low importance", importance=0.1)
    await save_memory(db_session, test_user_id, "High importance", importance=0.9)

    memories, total = await get_user_memories(
        db_session, test_user_id, min_importance=0.5
    )
    assert total >= 1
    for m in memories:
        assert m.importance >= 0.5


async def test_update_memory(db_session: AsyncSession, test_user_id: str) -> None:
    """Test updating a memory."""
    memory = await save_memory(db_session, test_user_id, "Original content")
    updated = await update_memory(
        db_session, memory.id, content="Updated content", importance=0.7
    )
    assert updated is not None
    assert updated.content == "Updated content"
    assert updated.importance == 0.7


async def test_delete_memory(db_session: AsyncSession, test_user_id: str) -> None:
    """Test deleting a memory."""
    memory = await save_memory(db_session, test_user_id, "To be deleted")
    deleted = await delete_memory(db_session, memory.id)
    assert deleted is True

    retrieved = await retrieve_memory(db_session, memory.id)
    assert retrieved is None


async def test_clear_user_memories(db_session: AsyncSession, test_user_id: str) -> None:
    """Test clearing all memories for a user."""
    await save_memory(db_session, test_user_id, "Memory 1")
    await save_memory(db_session, test_user_id, "Memory 2")

    count = await clear_user_memories(db_session, test_user_id)
    assert count == 2

    memories, total = await get_user_memories(db_session, test_user_id)
    assert total == 0


async def test_build_memory_context(db_session: AsyncSession, test_user_id: str) -> None:
    """Test building memory context string."""
    await save_memory(
        db_session, test_user_id, "User is a Python developer", importance=0.9
    )
    await save_memory(
        db_session, test_user_id, "User prefers VS Code", importance=0.7
    )

    context = await build_memory_context(db_session, test_user_id)
    assert "Python developer" in context
    assert "VS Code" in context


async def test_build_memory_context_empty(db_session: AsyncSession, test_user_id: str) -> None:
    """Test building memory context when there are no memories."""
    context = await build_memory_context(db_session, test_user_id)
    assert context == ""


async def test_summarize_conversation_short(db_session: AsyncSession, test_user_id: str) -> None:
    """Test that short conversations don't get summarized."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
    ]
    summary = await summarize_conversation(
        db_session, uuid.uuid4(), messages
    )
    assert summary is None


async def test_summarize_conversation_long(db_session: AsyncSession, test_user_id: str) -> None:
    """Test summarizing a conversation with enough messages."""
    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language."},
        {"role": "user", "content": "Can you show me an example?"},
        {"role": "assistant", "content": "Sure! print('Hello World')"},
    ]
    summary = await summarize_conversation(
        db_session, uuid.uuid4(), messages
    )
    assert summary is not None
    assert "Python" in summary or "python" in summary.lower()