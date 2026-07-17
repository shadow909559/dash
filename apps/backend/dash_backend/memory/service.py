"""Memory Service.

Provides long-term memory storage and retrieval for the AI assistant.
Memories are durable facts that persist across conversations, allowing
DASH to remember user preferences, personal information, and context.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.memory import Memory
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# CRUD Operations
# ──────────────────────────────────────────────


async def search_memories(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    q: str,
    *,
    limit: int = 10,
    min_importance: float = 0.0,
    category: str | None = None,
) -> list[Memory]:
    """Search memories for a user.

    Minimal implementation (no embeddings): uses case-insensitive
    substring match on Memory.content, ordered by importance.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    query_text = f"%{q}%"

    filters = [
        Memory.user_id == uid,
        Memory.importance >= min_importance,
        Memory.content.ilike(query_text),
    ]
    if category is not None:
        filters.append(Memory.category == category)

    stmt = (
        select(Memory)
        .where(*filters)
        .order_by(Memory.importance.desc(), Memory.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_memory(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    content: str,
    *,
    source: str | None = None,
    category: str | None = None,
    importance: float = 0.5,
) -> Memory:

    """Store a new memory for the user.

    Args:
        session: Database session.
        user_id: The user's UUID.
        content: The memory content (fact, preference, etc.).
        source: Optional source identifier (e.g. "conversation", "user_profile").
        importance: Importance score 0.0-1.0 (higher = more important).

    Returns:
        The created Memory record.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    memory = Memory(
        user_id=uid,
        content=content,
        source=source,
        category=category,
        importance=importance,
    )

    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    logger.debug("Saved memory %s for user %s", memory.id, uid)
    return memory


async def retrieve_memory(
    session: AsyncSession,
    memory_id: str | uuid.UUID,
) -> Memory | None:
    """Retrieve a single memory by its id."""
    mid = uuid.UUID(memory_id) if isinstance(memory_id, str) else memory_id
    return await session.get(Memory, mid)


async def get_user_memories(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
    min_importance: float = 0.0,
    category: str | None = None,
) -> tuple[list[Memory], int]:

    """List all memories for a user, ordered by importance (desc)."""
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    filters = [Memory.user_id == uid, Memory.importance >= min_importance]
    if category is not None:
        filters.append(Memory.category == category)




    count_q = select(func.count(Memory.id)).where(*filters)
    total = await session.scalar(count_q) or 0

    query = (
        select(Memory)
        .where(*filters)
        .order_by(Memory.importance.desc(), Memory.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(query)
    return list(result.scalars().all()), total



async def update_memory(
    session: AsyncSession,
    memory_id: str | uuid.UUID,
    **kwargs: Any,
) -> Memory | None:
    """Update an existing memory.

    Allowed fields: content, source, category, importance.
    """

    mid = uuid.UUID(memory_id) if isinstance(memory_id, str) else memory_id
    allowed = {"content", "importance", "source", "category"}

    update_data = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

    if not update_data:
        return await retrieve_memory(session, mid)

    stmt = update(Memory).where(Memory.id == mid).values(**update_data)
    await session.execute(stmt)
    await session.commit()
    return await retrieve_memory(session, mid)


async def delete_memory(
    session: AsyncSession,
    memory_id: str | uuid.UUID,
) -> bool:
    """Permanently delete a memory."""
    mid = uuid.UUID(memory_id) if isinstance(memory_id, str) else memory_id
    memory = await session.get(Memory, mid)
    if memory is None:
        return False
    await session.delete(memory)
    await session.commit()
    return True


async def clear_user_memories(
    session: AsyncSession,
    user_id: str | uuid.UUID,
) -> int:
    """Delete all memories for a user. Returns count of deleted memories."""
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    stmt = delete(Memory).where(Memory.user_id == uid)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


# ──────────────────────────────────────────────
# Context Building
# ──────────────────────────────────────────────


async def build_memory_context(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    max_memories: int = 10,
    min_importance: float = 0.3,
) -> str:
    """Build a context string from the user's most important memories.

    This string is injected into the system prompt so the AI is aware
    of user preferences, facts, and context across conversations.

    Args:
        session: Database session.
        user_id: The user's UUID.
        max_memories: Maximum number of memories to include.
        min_importance: Minimum importance threshold.

    Returns:
        A formatted string of memories, or empty string if none found.
    """
    memories, _ = await get_user_memories(
        session,
        user_id,
        limit=max_memories,
        min_importance=min_importance,
    )

    if not memories:
        return ""

    lines = ["Here is what I know about the user:"]
    for m in memories:
        lines.append(f"- {m.content}")
        if m.source:
            lines[-1] += f" (source: {m.source})"

    return "\n".join(lines)


async def extract_memories_from_conversation(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    conversation_id: str | uuid.UUID,
    messages: list[dict[str, str]],
) -> list[Memory]:
    """Extract and store important facts from a conversation.

    This is called after a conversation turn to identify and persist
    any important information the user shared.

    In a production system, this would use an LLM call to extract
    structured facts. For now, we use a heuristic approach.

    Args:
        session: Database session.
        user_id: The user's UUID.
        conversation_id: The conversation UUID.
        messages: List of message dicts with 'role' and 'content'.

    Returns:
        List of newly created Memory records.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    new_memories: list[Memory] = []

    # Simple heuristic: look for user messages that contain
    # statements about preferences or personal information
    preference_indicators = [
        "my name is",
        "i am",
        "i like",
        "i love",
        "i use",
        "i work",
        "i prefer",
        "my favorite",
        "i'm using",
        "i have",
        "my email",
        "my phone",
        "i live",
        "i study",
        "i code",
        "i program",
    ]

    for msg in messages:
        if msg.get("role") != "user":
            continue
        raw = msg.get("content", "").strip()
        if not raw:
            continue
        content = raw.lower()

        for indicator in preference_indicators:
            if indicator in content:
                # Extract the sentence containing the indicator
                sentences = content.replace("?", ".").replace("!", ".").split(".")
                for sentence in sentences:
                    if indicator in sentence.strip().lower():
                        candidate_text = sentence.strip().capitalize()

                        # Heuristic importance scoring: preference keywords get higher importance
                        base_importance = 0.45
                        if any(k in candidate_text.lower() for k in ("prefer", "like", "love", "favorite")):
                            importance = min(0.95, base_importance + 0.25)
                        elif any(k in candidate_text.lower() for k in ("use", "work", "code", "program")):
                            importance = min(0.9, base_importance + 0.15)
                        else:
                            importance = base_importance

                        # Skip low-importance one-off statements
                        if importance < 0.4:
                            break

                        # Duplicate detection: look for existing similar memories
                        dup_stmt = (
                            select(Memory)
                            .where(Memory.user_id == uid, Memory.content.ilike(f"%{candidate_text[:60]}%"))
                            .limit(1)
                        )
                        try:
                            dup_res = await session.execute(dup_stmt)
                            existing = dup_res.scalar_one_or_none()
                        except Exception:
                            existing = None

                        if existing:
                            # Update importance and content if the new candidate is slightly longer
                            new_importance = max(existing.importance or 0.0, importance)
                            update_stmt = (
                                update(Memory)
                                .where(Memory.id == existing.id)
                                .values(importance=new_importance, content=candidate_text if len(candidate_text) > len(existing.content or "") else existing.content)
                            )
                            await session.execute(update_stmt)
                            await session.commit()
                            await session.refresh(existing)
                            new_memories.append(existing)
                            break

                        # Create new memory
                        memory = Memory(
                            user_id=uid,
                            content=candidate_text,
                            source="conversation",
                            importance=importance,
                        )
                        session.add(memory)
                        new_memories.append(memory)
                        break
                break

    if new_memories:
        await session.commit()
        for m in new_memories:
            await session.refresh(m)
        logger.info("Extracted %d memories from conversation", len(new_memories))

    return new_memories


# ──────────────────────────────────────────────
# Summarization
# ──────────────────────────────────────────────


async def summarize_conversation(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    messages: list[dict[str, str]],
) -> str | None:
    """Generate a summary of a conversation.

    In production, this would call the LLM to generate a concise
    summary. For now, we create a simple extractive summary.

    Args:
        session: Database session.
        conversation_id: The conversation UUID.
        messages: List of message dicts with 'role' and 'content'.

    Returns:
        A summary string, or None if there aren't enough messages.
    """
    if len(messages) < 4:
        return None

    # Simple extractive summary: take first user message as topic
    # and count key topics
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    assistant_messages = [m["content"] for m in messages if m.get("role") == "assistant"]

    if not user_messages:
        return None

    topic = user_messages[0][:100] if user_messages else "General conversation"
    exchange_count = len(user_messages)

    summary = (
        f"Conversation summary: {exchange_count} exchanges. "
        f"Started with: \"{topic}\"."
    )

    if assistant_messages:
        # Add a brief note about the assistant's response
        first_response = assistant_messages[0][:150] if assistant_messages else ""
        if first_response:
            summary += f" Assistant responded about: \"{first_response}\"."

    return summary