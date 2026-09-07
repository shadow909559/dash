"""Tests for typed memory categories, decision recording, work context, and stats.

Part 9-10: typed memory (personal/preference/project/decision/experience)
with importance, confidence, source, and project association.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.memory.service import (
    MEMORY_TYPES,
    get_continue_context,
    get_memory_stats,
    get_project_memories,
    remember_decision,
    record_work_context,
    save_memory,
    save_typed_memory,
)

pytestmark = pytest.mark.asyncio


# ── Typed Memory Categories ────────────────────────────────────


async def test_save_typed_memory_personal(db_session: AsyncSession, test_user_id: str) -> None:
    """Save a 'personal' typed memory with confidence."""
    mem = await save_typed_memory(
        db_session, test_user_id, "User lives in Bangalore",
        "personal", importance=0.7, confidence=0.9,
        source="user_input",
    )
    assert mem.type == "Personal"
    assert mem.category == "personal"
    assert mem.importance == 0.7
    assert mem.confidence == 0.9
    assert mem.source == "user_input"
    assert mem.content == "User lives in Bangalore"


async def test_save_typed_memory_preference(db_session: AsyncSession, test_user_id: str) -> None:
    """Save a 'preference' typed memory."""
    mem = await save_typed_memory(
        db_session, test_user_id, "User prefers dark mode",
        "preference", importance=0.8, confidence=0.95,
    )
    assert mem.type == "Preference"
    assert mem.category == "preference"


async def test_save_typed_memory_with_project(db_session: AsyncSession, test_user_id: str) -> None:
    """Save a typed memory associated with a project."""
    proj_id = uuid.uuid4()
    mem = await save_typed_memory(
        db_session, test_user_id, "DASH uses FastAPI for the backend",
        "project", importance=0.6, confidence=0.85,
        project_id=proj_id, tags=["architecture", "backend"],
    )
    assert mem.project_id == proj_id
    assert mem.tags == ["architecture", "backend"]
    assert mem.type == "Project"


async def test_save_typed_memory_invalid_type(db_session: AsyncSession, test_user_id: str) -> None:
    """Invalid type should raise ValueError."""
    with pytest.raises(ValueError, match="Invalid memory type"):
        await save_typed_memory(
            db_session, test_user_id, "test", "invalid_type",
        )


async def test_memory_types_constant() -> None:
    """MEMORY_TYPES should define the five canonical categories."""
    expected = {"personal", "preference", "project", "decision", "experience"}
    assert set(MEMORY_TYPES.keys()) == expected


# ── Remember This Decision ─────────────────────────────────────


async def test_remember_decision_basic(db_session: AsyncSession, test_user_id: str) -> None:
    """Record a decision with rationale."""
    mem = await remember_decision(
        db_session, test_user_id,
        "Use SQLite for development",
        rationale="Faster to iterate, no external dependencies",
    )
    assert mem.type == "Decision"
    assert mem.category == "decision"
    assert "Decision: Use SQLite for development" in mem.content
    assert "Rationale: Faster to iterate" in mem.content
    assert "decision" in mem.tags
    assert mem.source == "decision_record"
    assert mem.importance == 0.7
    assert mem.confidence == 0.8


async def test_remember_decision_with_alternatives(db_session: AsyncSession, test_user_id: str) -> None:
    """Record a decision with alternatives."""
    mem = await remember_decision(
        db_session, test_user_id,
        "Use Pydantic v2",
        rationale="Better performance than v1",
        alternatives=["Marshmallow", "dataclasses"],
        importance=0.9, confidence=0.95,
    )
    assert "Alternatives considered: Marshmallow, dataclasses" in mem.content
    assert mem.importance == 0.9
    assert mem.confidence == 0.95


async def test_remember_decision_with_project(db_session: AsyncSession, test_user_id: str) -> None:
    """Record a decision associated with a project."""
    proj_id = uuid.uuid4()
    mem = await remember_decision(
        db_session, test_user_id,
        "Use Alembic for migrations",
        project_id=proj_id,
    )
    assert mem.project_id == proj_id


# ── Continue Where We Left Off ─────────────────────────────────


async def test_record_work_context(db_session: AsyncSession, test_user_id: str) -> None:
    """Record work context for resumption."""
    mem = await record_work_context(
        db_session, test_user_id,
        task="Implementing typed memory",
        progress="Model and service done, tests pending",
        blockers=["Windows line ending issues"],
        next_steps=["Write tests", "Run full suite"],
    )
    assert mem.type == "Experience"
    assert mem.category == "experience"
    assert "Working on: Implementing typed memory" in mem.content
    assert "Progress: Model and service done" in mem.content
    assert "Blockers: Windows line ending issues" in mem.content
    assert "Next steps: Write tests, Run full suite" in mem.content
    assert mem.source == "work_context"
    assert "work_context" in mem.tags
    assert "resume" in mem.tags
    assert mem.importance == 0.6
    assert mem.confidence == 0.9


async def test_record_work_context_minimal(db_session: AsyncSession, test_user_id: str) -> None:
    """Record work context with only a task (minimal fields)."""
    mem = await record_work_context(
        db_session, test_user_id,
        task="Fix the build",
    )
    assert "Working on: Fix the build" in mem.content
    # Should not contain Progress/Blockers/Next steps
    assert "Progress:" not in mem.content
    assert "Blockers:" not in mem.content


async def test_get_continue_context(db_session: AsyncSession, test_user_id: str) -> None:
    """Retrieve recent work contexts."""
    # Record two work contexts
    await record_work_context(db_session, test_user_id, task="Task A", progress="half done")
    await record_work_context(db_session, test_user_id, task="Task B", progress="just started")

    contexts = await get_continue_context(db_session, test_user_id)
    assert len(contexts) == 2
    # Most recent first
    assert "Task B" in contexts[0].content
    assert "Task A" in contexts[1].content


async def test_get_continue_context_by_project(db_session: AsyncSession, test_user_id: str) -> None:
    """Filter work contexts by project."""
    proj_a = uuid.uuid4()
    proj_b = uuid.uuid4()
    await record_work_context(db_session, test_user_id, task="A1", project_id=proj_a)
    await record_work_context(db_session, test_user_id, task="B1", project_id=proj_b)
    await record_work_context(db_session, test_user_id, task="A2", project_id=proj_a)

    contexts = await get_continue_context(db_session, test_user_id, project_id=proj_a)
    assert len(contexts) == 2
    # Most recent first
    assert "A2" in contexts[0].content
    assert "A1" in contexts[1].content


# ── Project Memory Retrieval ───────────────────────────────────


async def test_get_project_memories(db_session: AsyncSession, test_user_id: str) -> None:
    """Retrieve memories by project."""
    proj_id = uuid.uuid4()
    await save_memory(
        db_session, test_user_id, "Backend uses FastAPI",
        memory_type="Project", importance=0.7, project_id=proj_id,
    )
    await save_memory(
        db_session, test_user_id, "User prefers dark mode",
        memory_type="Preference", importance=0.8, project_id=None,
    )
    mems = await get_project_memories(db_session, test_user_id, proj_id)
    assert len(mems) == 1
    assert "FastAPI" in mems[0].content


async def test_get_project_memories_filtered(db_session: AsyncSession, test_user_id: str) -> None:
    """Filter project memories by type."""
    proj_id = uuid.uuid4()
    await remember_decision(db_session, test_user_id, "Use SQLite", project_id=proj_id)
    await remember_decision(db_session, test_user_id, "Use Alembic", project_id=proj_id)
    await record_work_context(db_session, test_user_id, task="Build API", project_id=proj_id)

    decisions = await get_project_memories(
        db_session, test_user_id, proj_id, memory_type="Decision",
    )
    assert len(decisions) == 2
    assert all(m.type == "Decision" for m in decisions)


# ── Memory Stats ───────────────────────────────────────────────


async def test_get_memory_stats(db_session: AsyncSession, test_user_id: str) -> None:
    """Memory stats should aggregate correctly."""
    await save_typed_memory(
        db_session, test_user_id, "User lives in Bangalore",
        "personal", importance=0.7, confidence=0.9,
    )
    await save_typed_memory(
        db_session, test_user_id, "User prefers dark mode",
        "preference", importance=0.8, confidence=0.85,
    )
    await remember_decision(
        db_session, test_user_id, "Use SQLite", importance=0.6, confidence=0.7,
    )

    stats = await get_memory_stats(db_session, test_user_id)
    assert stats["total"] >= 3
    assert stats["by_type"].get("Personal", 0) >= 1
    assert stats["by_type"].get("Preference", 0) >= 1
    assert stats["by_type"].get("Decision", 0) >= 1
    assert 0.0 < stats["avg_importance"] <= 1.0
    assert 0.0 < stats["avg_confidence"] <= 1.0


async def test_get_memory_stats_empty(db_session: AsyncSession, test_user_id: str) -> None:
    """Stats for a user with no memories should return zeros."""
    stats = await get_memory_stats(db_session, test_user_id)
    assert stats["total"] == 0
    assert stats["by_type"] == {}
    assert stats["avg_importance"] == 0.0
    assert stats["avg_confidence"] == 0.5  # default
    assert stats["project_count"] == 0


async def test_get_memory_stats_project_count(db_session: AsyncSession, test_user_id: str) -> None:
    """Project count should reflect distinct projects."""
    proj_a = uuid.uuid4()
    proj_b = uuid.uuid4()
    await save_memory(db_session, test_user_id, "A", project_id=proj_a)
    await save_memory(db_session, test_user_id, "B", project_id=proj_a)
    await save_memory(db_session, test_user_id, "C", project_id=proj_b)

    stats = await get_memory_stats(db_session, test_user_id)
    assert stats["project_count"] == 2


# ── Confidence and Project ID in save_memory ───────────────────


async def test_save_memory_with_confidence(db_session: AsyncSession, test_user_id: str) -> None:
    """save_memory should accept and store confidence."""
    mem = await save_memory(
        db_session, test_user_id, "Test confidence",
        confidence=0.3,
    )
    assert mem.confidence == 0.3


async def test_save_memory_confidence_clamped(db_session: AsyncSession, test_user_id: str) -> None:
    """Confidence should be clamped to [0, 1]."""
    mem = await save_memory(
        db_session, test_user_id, "Test clamping",
        confidence=1.5,
    )
    assert mem.confidence == 1.0


async def test_save_memory_with_project_id(db_session: AsyncSession, test_user_id: str) -> None:
    """save_memory should accept and store project_id."""
    proj_id = uuid.uuid4()
    mem = await save_memory(
        db_session, test_user_id, "Test project association",
        project_id=proj_id,
    )
    assert mem.project_id == proj_id
