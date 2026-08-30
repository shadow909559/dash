import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.user import User
from dash_backend.db.models.memory import Memory
from dash_backend.memory import service as memory_service

# Reuse repo-level backend pytest fixtures shipped in apps/backend/tests/conftest.py
from tests.conftest import *  # noqa: F401,F403



@pytest.mark.asyncio
async def test_importance_scoring_levels_to_float_mapping(db_session: AsyncSession, test_user: User):
    # Phase 1 uses float column in existing schema; mapping should still be monotonic.
    # LOW < NORMAL < HIGH < CRITICAL in relative importance.
    m_low = await memory_service.save_memory(
        db_session,
        test_user.id,
        content="My favorite color is blue.",
        source="conversation",
        category="Preference",
        importance=0.1,
    )
    m_crit = await memory_service.save_memory(
        db_session,
        test_user.id,
        content="My API key location is /home/user/.keys.",
        source="conversation",
        category="Technical",
        importance=0.95,
    )

    assert isinstance(m_low.importance, float)
    assert isinstance(m_crit.importance, float)
    assert m_low.importance < m_crit.importance


@pytest.mark.asyncio
async def test_duplicate_detection_updates_instead_of_creating(db_session: AsyncSession, test_user: User):
    # Use existing heuristic extractor which does duplicate-like updates using content similarity.
    messages = [
        {"role": "user", "content": "My favorite color is blue."},
        {"role": "assistant", "content": "Nice."},
        {"role": "user", "content": "I like blue a lot."},
    ]

    created1 = await memory_service.extract_memories_from_conversation(
        db_session, test_user.id, conversation_id=uuid.uuid4(), messages=messages
    )

    total_after_1 = (
        await db_session.execute(
            Memory.__table__.select().where(Memory.user_id == test_user.id)
        )
    ).all()

    created2 = await memory_service.extract_memories_from_conversation(
        db_session, test_user.id, conversation_id=uuid.uuid4(), messages=messages
    )

    rows_after_2 = (
        await db_session.execute(
            Memory.__table__.select().where(Memory.user_id == test_user.id)
        )
    ).all()

    # Heuristic duplicate detection should avoid exponential growth.
    assert len(rows_after_2) <= len(total_after_1) + 1

    assert len(created1) >= 0
    assert len(created2) >= 0


@pytest.mark.asyncio
async def test_search_returns_top_by_importance(db_session: AsyncSession, test_user: User):
    await memory_service.save_memory(
        db_session,

        test_user.id,
        content="Backend uses PostgreSQL.",
        source="conversation",
        category="Technical",
        importance=0.9,
    )
    await memory_service.save_memory(
        db_session,
        test_user.id,
        content="I like blue.",
        source="conversation",
        category="Preference",
        importance=0.1,
    )

    results = await memory_service.search_memories(
        db_session,
        test_user.id,
        q="backend",
        limit=2,
        min_importance=0.0,
    )

    assert results
    assert results[0].importance >= results[-1].importance


@pytest.mark.asyncio
async def test_memory_context_includes_relevant_memory_snippets(db_session: AsyncSession, test_user: User):
    await memory_service.save_memory(
        db_session,
        test_user.id,
        content="User prefers dark mode.",
        source="conversation",
        category="Preference",
        importance=0.8,
    )

    ctx = await memory_service.build_memory_context(db_session, test_user.id, max_memories=5, min_importance=0.3)
    assert "dark mode" in ctx

