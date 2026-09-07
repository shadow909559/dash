"""Personality profile service.

Provides persistent personality profile for users, including preferences,
coding style, goals, and personal facts. The profile is built from memories
and updated automatically as new information is learned.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.memory import Memory
from dash_backend.logging_config import get_logger
from dash_backend.memory.service import save_memory

logger = get_logger(__name__)

# Personality profile categories
PERSONALITY_CATEGORIES = {
    "preference": "Preference",
    "coding_style": "CodingStyle",
    "goal": "Goal",
    "project": "Project",
    "person": "Person",
    "fact": "Fact",
    "habit": "Habit",
}


async def get_personality_profile(
    session: AsyncSession,
    user_id: str | uuid.UUID,
) -> dict[str, Any]:
    """Build a personality profile from the user's memories.

    Returns a structured dict with categories of personal information.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    profile: dict[str, Any] = {
        "preferences": [],
        "coding_style": [],
        "goals": [],
        "projects": [],
        "people": [],
        "facts": [],
        "habits": [],
    }

    # Fetch all high-importance memories
    stmt = (
        select(Memory)
        .where(
            Memory.user_id == uid,
            Memory.importance >= 0.3,
        )
        .order_by(Memory.importance.desc())
        .limit(200)
    )
    result = await session.execute(stmt)
    memories: list[Memory] = list(result.scalars().all())

    for mem in memories:
        entry = {
            "content": mem.content,
            "importance": mem.importance,
            "source": mem.source,
            "created_at": mem.created_at.isoformat() if mem.created_at else None,
        }

        mem_type = (mem.type or "").lower()
        category = (mem.category or "").lower()

        if mem_type == "preference" or category == "preference":
            profile["preferences"].append(entry)
        elif mem_type == "goal" or category == "goal":
            profile["goals"].append(entry)
        elif mem_type == "project" or category == "project":
            profile["projects"].append(entry)
        elif mem_type == "person" or category == "person":
            profile["people"].append(entry)
        elif mem_type == "habit" or category == "habit":
            profile["habits"].append(entry)
        elif "code" in mem_type.lower() or "style" in mem_type.lower():
            profile["coding_style"].append(entry)
        else:
            profile["facts"].append(entry)

    return profile


async def update_preferences(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    preferences: list[dict[str, Any]],
) -> int:
    """Update user preferences from a list of preference dicts.

    Each dict should have:
    - content: str (the preference statement)
    - importance: float (0.0-1.0, optional, default 0.5)

    Returns the number of preferences saved.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    count = 0

    for pref in preferences:
        content = pref.get("content", "").strip()
        if not content:
            continue

        importance = min(1.0, max(0.0, pref.get("importance", 0.5)))

        await save_memory(
            session, uid, content,
            source="preference_update",
            category="Preference",
            importance=importance,
            memory_type="Preference",
        )
        count += 1

    if count:
        logger.info("Updated %d preferences for user %s", count, uid)

    return count


async def learn_from_conversation(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    conversation_id: str | uuid.UUID,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    """Learn personality traits and preferences from a conversation.

    Extracts preferences, goals, and personal facts from the conversation
    and stores them as memories. Returns a summary of what was learned.
    """
    from dash_backend.memory.service import extract_memories_from_conversation

    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    # Extract memories using existing heuristic
    new_memories = await extract_memories_from_conversation(
        session, uid, conversation_id, messages
    )

    # Build learning summary
    learned: dict[str, Any] = {
        "new_memories": len(new_memories),
        "preferences": 0,
        "goals": 0,
        "facts": 0,
    }

    for mem in new_memories:
        mem_type = (mem.type or "").lower()
        if mem_type == "preference":
            learned["preferences"] += 1
        elif mem_type == "goal":
            learned["goals"] += 1
        else:
            learned["facts"] += 1

    return learned


async def get_preference_summary(
    session: AsyncSession,
    user_id: str | uuid.UUID,
) -> str:
    """Get a concise summary of user preferences for prompt injection.

    Returns a formatted string of the user's top preferences.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    stmt = (
        select(Memory)
        .where(
            Memory.user_id == uid,
            Memory.type == "Preference",
            Memory.importance >= 0.4,
        )
        .order_by(Memory.importance.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    preferences: list[Memory] = list(result.scalars().all())

    if not preferences:
        return ""

    lines = ["User preferences:"]
    for pref in preferences:
        line = f"- {pref.content}"
        if pref.importance and pref.importance > 0.7:
            line += " [strong preference]"
        lines.append(line)

    return "\n".join(lines)