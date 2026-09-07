"""Tests for personality profile, preference learning, and memory summarization."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.memory.personality import (
    get_personality_profile,
    update_preferences,
    learn_from_conversation,
    get_preference_summary,
)
from dash_backend.memory.service import summarize_conversation
from dash_backend.db.models.memory import Memory


# ──────────────────────────────────────────────
# Personality Profile
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_personality_profile_empty():
    """Test that empty profile returns empty categories."""
    session = AsyncMock(spec=AsyncSession)

    # Mock execute to return empty result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    profile = await get_personality_profile(session, user_id=uuid.uuid4())

    assert isinstance(profile, dict)
    assert profile["preferences"] == []
    assert profile["goals"] == []
    assert profile["facts"] == []
    assert profile["projects"] == []
    assert profile["people"] == []


@pytest.mark.asyncio
async def test_get_personality_profile_with_preferences():
    """Test that preferences are correctly categorized."""
    session = AsyncMock(spec=AsyncSession)

    # Create mock memories
    pref_memory = MagicMock(spec=Memory)
    pref_memory.content = "User prefers Python"
    pref_memory.importance = 0.8
    pref_memory.source = "conversation"
    pref_memory.type = "Preference"
    pref_memory.category = "Preference"
    pref_memory.created_at = None

    goal_memory = MagicMock(spec=Memory)
    goal_memory.content = "User wants to learn Rust"
    goal_memory.importance = 0.9
    goal_memory.source = "conversation"
    goal_memory.type = "Goal"
    goal_memory.category = "Goal"
    goal_memory.created_at = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pref_memory, goal_memory]
    session.execute.return_value = mock_result

    profile = await get_personality_profile(session, user_id=uuid.uuid4())

    assert len(profile["preferences"]) == 1
    assert profile["preferences"][0]["content"] == "User prefers Python"
    assert len(profile["goals"]) == 1
    assert profile["goals"][0]["content"] == "User wants to learn Rust"


@pytest.mark.asyncio
async def test_update_preferences():
    """Test that preferences are saved as memories."""
    session = AsyncMock(spec=AsyncSession)

    with patch("dash_backend.memory.personality.save_memory") as mock_save:
        mock_save.return_value = MagicMock(spec=Memory)

        preferences = [
            {"content": "User likes dark mode", "importance": 0.8},
            {"content": "User prefers VS Code", "importance": 0.7},
        ]

        count = await update_preferences(session, user_id=uuid.uuid4(), preferences=preferences)

        assert count == 2
        assert mock_save.call_count == 2
        # Verify correct call arguments
        _, kwargs = mock_save.call_args_list[0]
        assert kwargs["source"] == "preference_update"
        assert kwargs["category"] == "Preference"
        assert kwargs["memory_type"] == "Preference"


@pytest.mark.asyncio
async def test_update_preferences_empty():
    """Test empty preferences list."""
    session = AsyncMock(spec=AsyncSession)

    with patch("dash_backend.memory.personality.save_memory") as mock_save:
        count = await update_preferences(session, user_id=uuid.uuid4(), preferences=[])
        assert count == 0
        mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_get_preference_summary_with_prefs():
    """Test preference summary generation."""
    session = AsyncMock(spec=AsyncSession)

    pref_memory = MagicMock(spec=Memory)
    pref_memory.content = "User likes Python"
    pref_memory.importance = 0.9
    pref_memory.type = "Preference"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [pref_memory]
    session.execute.return_value = mock_result

    summary = await get_preference_summary(session, user_id=uuid.uuid4())

    assert "User preferences:" in summary
    assert "User likes Python" in summary
    assert "[strong preference]" in summary  # importance > 0.7


@pytest.mark.asyncio
async def test_get_preference_summary_empty():
    """Test empty preference summary."""
    session = AsyncMock(spec=AsyncSession)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    summary = await get_preference_summary(session, user_id=uuid.uuid4())
    assert summary == ""


@pytest.mark.asyncio
async def test_learn_from_conversation():
    """Test learning from conversation."""
    session = AsyncMock(spec=AsyncSession)
    uid = uuid.uuid4()
    conv_id = uuid.uuid4()

    messages = [
        {"role": "user", "content": "My name is Alice and I like Python"},
        {"role": "assistant", "content": "Hello Alice! Python is great."},
    ]

    with patch("dash_backend.memory.service.extract_memories_from_conversation") as mock_extract:
        mock_memory = MagicMock(spec=Memory)
        mock_memory.type = "Preference"
        mock_memory.content = "Alice likes Python"
        mock_extract.return_value = [mock_memory]

        result = await learn_from_conversation(
            session, uid, conv_id, messages
        )

        assert result["new_memories"] == 1
        assert result["preferences"] == 1
        mock_extract.assert_called_once_with(session, uid, conv_id, messages)


# ──────────────────────────────────────────────
# Summarization saved as memory
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_summarize_conversation_saves_memory():
    """Test that summarization saves memory when save_as_memory=True."""
    session = AsyncMock(spec=AsyncSession)
    uid = uuid.uuid4()
    conv_id = uuid.uuid4()

    messages = [
        {"role": "user", "content": "Hello, I want to learn Python"},
        {"role": "assistant", "content": "Great choice! Let me help you."},
        {"role": "user", "content": "I have experience with JavaScript"},
        {"role": "assistant", "content": "That will help you learn faster."},
        {"role": "user", "content": "What's the best way to start?"},
        {"role": "assistant", "content": "Start with basics like variables and loops."},
        {"role": "user", "content": "I prefer video tutorials"},
        {"role": "assistant", "content": "There are excellent Python video courses."},
    ]

    with patch("dash_backend.memory.service.save_memory") as mock_save:
        mock_save.return_value = MagicMock(spec=Memory)

        summary = await summarize_conversation(
            session, conv_id, messages,
            user_id=uid,
            save_as_memory=True,
        )

        assert summary is not None
        assert "Python" in summary
        mock_save.assert_called_once()
        _, kwargs = mock_save.call_args
        assert kwargs["source"] == "conversation_summary"
        assert kwargs["category"] == "Summary"
        assert kwargs["memory_type"] == "Summary"
        assert kwargs["importance"] == 0.6


@pytest.mark.asyncio
async def test_summarize_conversation_no_save():
    """Test that summarization does NOT save memory when save_as_memory=False."""
    session = AsyncMock(spec=AsyncSession)
    conv_id = uuid.uuid4()

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "I'm fine."},
        {"role": "user", "content": "Good"},
        {"role": "assistant", "content": "Great!"},
        {"role": "user", "content": "Bye"},
        {"role": "assistant", "content": "Goodbye!"},
    ]

    with patch("dash_backend.memory.service.save_memory") as mock_save:
        summary = await summarize_conversation(
            session, conv_id, messages,
            save_as_memory=False,
        )

        assert summary is not None
        mock_save.assert_not_called()


@pytest.mark.asyncio
async def test_summarize_conversation_too_short():
    """Test that summarization returns None for short conversations."""
    session = AsyncMock(spec=AsyncSession)
    conv_id = uuid.uuid4()

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
    ]

    summary = await summarize_conversation(
        session, conv_id, messages,
        user_id=uuid.uuid4(),
        save_as_memory=True,
    )

    assert summary is None


@pytest.mark.asyncio
async def test_summarize_conversation_no_user_id():
    """Test that summarize works when user_id is None."""
    session = AsyncMock(spec=AsyncSession)
    conv_id = uuid.uuid4()

    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi!"},
        {"role": "user", "content": "How are you?"},
        {"role": "assistant", "content": "Fine."},
        {"role": "user", "content": "Good day"},
        {"role": "assistant", "content": "Indeed."},
        {"role": "user", "content": "Bye"},
        {"role": "assistant", "content": "Goodbye!"},
    ]

    summary = await summarize_conversation(
        session, conv_id, messages,
        user_id=None,
        save_as_memory=True,
    )

    assert summary is not None


# ──────────────────────────────────────────────
# Planner with memory context
# ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_planner_decompose_with_memory_context():
    """Test that planner accepts memory_context parameter."""
    from dash_backend.executive.planner import Planner

    # When no LLM is configured, fallback should still work
    items = await Planner.decompose(
        "Test Goal",
        "Do A. Do B.",
        memory_context="User prefers Python and has experience with web development",
    )
    assert isinstance(items, list)
    assert len(items) >= 1
    assert "name" in items[0]


@pytest.mark.asyncio
async def test_planner_decompose_json_with_memory():
    """Test that planner parses JSON with memory context."""
    from dash_backend.executive.planner import Planner

    json_desc = '[{"name": "Task 1", "description": "First"}, {"name": "Task 2", "description": "Second"}]'
    items = await Planner.decompose(
        "Goal",
        json_desc,
        memory_context="User prefers Python",
    )
    assert isinstance(items, list)
    assert items[0]["name"] == "Task 1"


# ──────────────────────────────────────────────
# Integration: Memory -> Chat -> Summarization
# ──────────────────────────────────────────────


def test_build_chat_messages_includes_memory_context():
    """Test that memory context is properly injected into chat messages."""
    from dash_backend.llm.service import build_chat_messages

    memory_context = "Here is what I know about the user:\n- User prefers Python over JavaScript"

    messages = build_chat_messages(
        system_prompt="You are DASH.",
        user_message="What language should I use?",
        memory_context=memory_context,
    )

    assert len(messages) >= 2
    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "[USER MEMORY CONTEXT]" in system_msg["content"]
    assert "User prefers Python over JavaScript" in system_msg["content"]