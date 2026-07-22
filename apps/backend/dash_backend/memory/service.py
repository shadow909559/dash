"""Memory Service.

Provides long-term memory storage and retrieval for the AI assistant.
Memories are durable facts that persist across conversations, allowing
DASH to remember user preferences, personal information, and context.

Supports:
- CRUD operations
- Semantic retrieval (via embeddings)
- Lexical fallback (substring search)
- Hybrid ranking (semantic + importance + recency + access frequency)
- Duplicate detection
- Memory pruning
- Conversation summaries
- Automatic prompt injection
"""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.memory import Memory
from dash_backend.logging_config import get_logger
from dash_backend.memory.embeddings import get_embedding

logger = get_logger(__name__)

# ──────────────────────────────────────────────
# Scoring Constants
# ──────────────────────────────────────────────

# Weights for hybrid ranking
WEIGHT_SEMANTIC = 0.40
WEIGHT_IMPORTANCE = 0.30
WEIGHT_RECENCY = 0.20
WEIGHT_FREQUENCY = 0.10

# Decay constants
RECENCY_HALF_LIFE_DAYS = 14.0  # memories lose half their recency score after 14 days
FREQUENCY_MAX = 50  # cap access count for normalization

# Pruning
MAX_MEMORIES_PER_USER = 500
PRUNE_BATCH_SIZE = 50


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _compute_hybrid_score(
    semantic_sim: float,
    importance: float,
    age_days: float,
    access_count: int,
) -> float:
    """Compute hybrid ranking score.

    Combines:
    - Semantic similarity (0-1)
    - Importance (0-1)
    - Recency (exponential decay)
    - Access frequency (capped and normalized)
    """
    recency = math.exp(-age_days / RECENCY_HALF_LIFE_DAYS)
    frequency = min(access_count, FREQUENCY_MAX) / FREQUENCY_MAX

    score = (
        WEIGHT_SEMANTIC * max(0.0, semantic_sim)
        + WEIGHT_IMPORTANCE * importance
        + WEIGHT_RECENCY * recency
        + WEIGHT_FREQUENCY * frequency
    )
    return score


async def _update_access_stats(session: AsyncSession, memory: Memory) -> None:
    """Update access tracking for a memory."""
    memory.access_count = (memory.access_count or 0) + 1
    memory.last_accessed = datetime.now(UTC)
    session.add(memory)
    await session.commit()


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
    """Search memories for a user using hybrid retrieval.

    Uses semantic search if embeddings are available, falls back to
    lexical (substring) search. Results are ranked by hybrid score.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    # Try semantic search first
    query_emb = await get_embedding(q)

    if query_emb is not None:
        return await _semantic_search(
            session, uid, q, query_emb,
            limit=limit, min_importance=min_importance, category=category,
        )

    # Fallback: lexical search
    return await _lexical_search(
        session, uid, q,
        limit=limit, min_importance=min_importance, category=category,
    )


async def _semantic_search(
    session: AsyncSession,
    user_id: uuid.UUID,
    q: str,
    query_emb: list[float],
    *,
    limit: int = 10,
    min_importance: float = 0.0,
    category: str | None = None,
) -> list[Memory]:
    """Semantic search with hybrid ranking."""
    # Fetch candidate memories (with embeddings)
    filters = [
        Memory.user_id == user_id,
        Memory.importance >= min_importance,
        Memory.embedding.isnot(None),
    ]
    if category is not None:
        filters.append(Memory.category == category)

    stmt = (
        select(Memory)
        .where(*filters)
        .order_by(Memory.importance.desc(), Memory.created_at.desc())
        .limit(200)  # candidate pool
    )
    result = await session.execute(stmt)
    candidates: list[Memory] = list(result.scalars().all())

    if not candidates:
        # Fallback to lexical if no embeddings
        return await _lexical_search(
            session, user_id, q,
            limit=limit, min_importance=min_importance, category=category,
        )

    now = datetime.now(UTC)
    scored: list[tuple[Memory, float]] = []

    for mem in candidates:
        semantic_sim = _cosine_similarity(query_emb, mem.embedding or [])

        # Also do lexical match as a boost for exact matches
        lexical_boost = 0.0
        if q.lower() in (mem.content or "").lower():
            lexical_boost = 0.2

        age_days = 0.0
        if mem.created_at:
            age_days = max(0.0, (now - mem.created_at).total_seconds() / 86400.0)

        access_count = mem.access_count or 0
        importance = mem.importance or 0.0

        hybrid = _compute_hybrid_score(
            semantic_sim + lexical_boost,
            importance,
            age_days,
            access_count,
        )
        scored.append((mem, hybrid))

    # Sort by hybrid score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # Update access stats for returned memories
    results = [mem for mem, _ in scored[:limit]]
    for mem in results:
        try:
            await _update_access_stats(session, mem)
        except Exception:
            pass

    return results


async def _lexical_search(
    session: AsyncSession,
    user_id: uuid.UUID,
    q: str,
    *,
    limit: int = 10,
    min_importance: float = 0.0,
    category: str | None = None,
) -> list[Memory]:
    """Lexical (substring) search fallback."""
    query_text = f"%{q}%"

    filters = [
        Memory.user_id == user_id,
        Memory.importance >= min_importance,
        or_(
            Memory.content.ilike(query_text),
            Memory.title.ilike(query_text),
        ),
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
    memories = list(result.scalars().all())

    # Update access stats
    for mem in memories:
        try:
            await _update_access_stats(session, mem)
        except Exception:
            pass

    return memories


async def save_memory(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    content: str,
    *,
    source: str | None = None,
    category: str | None = None,
    importance: float = 0.5,
    memory_type: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
    conversation_id: str | uuid.UUID | None = None,
) -> Memory:
    """Store a new memory for the user.

    Automatically generates embedding if provider is configured.
    Performs duplicate detection before creating.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    # Duplicate detection: check for similar existing memory
    dup_stmt = (
        select(Memory)
        .where(
            Memory.user_id == uid,
            Memory.content.ilike(f"%{content[:80]}%"),
        )
        .limit(1)
    )
    dup_res = await session.execute(dup_stmt)
    existing = dup_res.scalar_one_or_none()

    if existing:
        # Update existing memory with higher importance and new content
        new_importance = max(existing.importance or 0.0, importance)
        if len(content) > len(existing.content or ""):
            existing.content = content
        existing.importance = new_importance
        if title:
            existing.title = title
        if tags:
            existing.tags = tags
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        logger.debug("Updated existing memory %s for user %s", existing.id, uid)
        return existing

    # Resolve memory type
    resolved_type = memory_type
    if resolved_type is None:
        cat = (category or "").lower()
        resolved_type = "Fact"
        type_map = {
            "preference": "Preference",
            "preferences": "Preference",
            "conversation": "Conversation",
            "task": "Task",
            "project": "Project",
            "person": "Person",
            "goal": "Goal",
            "summary": "Summary",
            "fact": "Fact",
        }
        resolved_type = type_map.get(cat, "Fact")

    # Generate title from content if not provided
    if not title:
        title = content[:120] if len(content) > 120 else content

    memory = Memory(
        user_id=uid,
        type=resolved_type,
        title=title,
        content=content,
        source=source,
        category=category,
        importance=importance,
        tags=tags or [],
        conversation_id=uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id,
    )

    session.add(memory)
    await session.commit()
    await session.refresh(memory)

    # Generate embedding asynchronously (best-effort)
    try:
        emb = await get_embedding(content)
        if emb:
            memory.embedding = emb
            session.add(memory)
            await session.commit()
            await session.refresh(memory)
    except Exception:
        logger.exception("Failed to generate embedding for memory %s", memory.id)

    logger.debug("Saved memory %s for user %s", memory.id, uid)
    return memory


async def retrieve_memory(
    session: AsyncSession,
    memory_id: str | uuid.UUID,
) -> Memory | None:
    """Retrieve a single memory by its id."""
    mid = uuid.UUID(memory_id) if isinstance(memory_id, str) else memory_id
    memory = await session.get(Memory, mid)
    if memory:
        try:
            await _update_access_stats(session, memory)
        except Exception:
            pass
    return memory


async def get_user_memories(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
    min_importance: float = 0.0,
    category: str | None = None,
    memory_type: str | None = None,
    sort_by: str = "importance",  # importance, recency, frequency
) -> tuple[list[Memory], int]:
    """List all memories for a user with flexible sorting."""
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    filters = [Memory.user_id == uid, Memory.importance >= min_importance]
    if category is not None:
        filters.append(Memory.category == category)
    if memory_type is not None:
        filters.append(Memory.type == memory_type)

    count_q = select(func.count(Memory.id)).where(*filters)
    total = await session.scalar(count_q) or 0

    # Determine sort order
    if sort_by == "recency":
        order = Memory.created_at.desc()
    elif sort_by == "frequency":
        order = Memory.access_count.desc()
    else:  # importance (default)
        order = Memory.importance.desc()

    query = (
        select(Memory)
        .where(*filters)
        .order_by(order, Memory.created_at.desc())
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

    Allowed fields: content, title, source, category, importance, tags.
    """
    mid = uuid.UUID(memory_id) if isinstance(memory_id, str) else memory_id
    allowed = {"content", "title", "importance", "source", "category", "tags"}

    update_data = {k: v for k, v in kwargs.items() if k in allowed and v is not None}

    if not update_data:
        return await retrieve_memory(session, mid)

    stmt = update(Memory).where(Memory.id == mid).values(**update_data)
    await session.execute(stmt)
    await session.commit()

    # Regenerate embedding if content changed
    if "content" in update_data:
        try:
            memory = await session.get(Memory, mid)
            if memory:
                emb = await get_embedding(memory.content)
                if emb:
                    memory.embedding = emb
                    session.add(memory)
                    await session.commit()
        except Exception:
            logger.exception("Failed to regenerate embedding for memory %s", mid)

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
# Memory Pruning
# ──────────────────────────────────────────────


async def prune_memories(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    max_memories: int = MAX_MEMORIES_PER_USER,
) -> int:
    """Prune old/low-importance memories when the user exceeds the limit.

    Removes the lowest-scoring memories using hybrid ranking.
    Returns the number of memories pruned.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    # Count current memories
    count_q = select(func.count(Memory.id)).where(Memory.user_id == uid)
    total = await session.scalar(count_q) or 0

    if total <= max_memories:
        return 0

    excess = total - max_memories
    prune_count = min(excess, PRUNE_BATCH_SIZE)

    # Fetch all memories for scoring
    stmt = (
        select(Memory)
        .where(Memory.user_id == uid)
        .order_by(Memory.created_at.desc())
    )
    result = await session.execute(stmt)
    all_memories: list[Memory] = list(result.scalars().all())

    if not all_memories:
        return 0

    now = datetime.now(UTC)
    scored: list[tuple[Memory, float]] = []

    for mem in all_memories:
        age_days = 0.0
        if mem.created_at:
            age_days = max(0.0, (now - mem.created_at).total_seconds() / 86400.0)

        access_count = mem.access_count or 0
        importance = mem.importance or 0.0

        # Score without semantic (no query context for pruning)
        score = _compute_hybrid_score(0.0, importance, age_days, access_count)
        scored.append((mem, score))

    # Sort by score ascending (lowest first)
    scored.sort(key=lambda x: x[1])

    # Remove lowest-scoring memories
    to_remove = [mem for mem, _ in scored[:prune_count]]
    for mem in to_remove:
        await session.delete(mem)

    await session.commit()
    logger.info("Pruned %d memories for user %s", len(to_remove), uid)
    return len(to_remove)


# ──────────────────────────────────────────────
# Context Building
# ──────────────────────────────────────────────


async def build_memory_context(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    *,
    max_memories: int = 10,
    min_importance: float = 0.3,
    query: str | None = None,
) -> str:
    """Build a context string from the user's most relevant memories.

    If a query is provided, uses semantic search. Otherwise returns
    the most important recent memories.

    This string is injected into the system prompt so the AI is aware
    of user preferences, facts, and context across conversations.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    if query:
        memories = await search_memories(
            session, uid, query,
            limit=max_memories,
            min_importance=min_importance,
        )
    else:
        memories, _ = await get_user_memories(
            session, uid,
            limit=max_memories,
            min_importance=min_importance,
            sort_by="importance",
        )

    if not memories:
        return ""

    lines = ["Here is what I know about the user:"]
    for m in memories:
        line = f"- {m.content}"
        if m.source:
            line += f" (source: {m.source})"
        if m.importance and m.importance > 0.7:
            line += " [important]"
        lines.append(line)

    return "\n".join(lines)


async def extract_memories_from_conversation(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    conversation_id: str | uuid.UUID,
    messages: list[dict[str, str]],
) -> list[Memory]:
    """Extract and store important facts from a conversation.

    Uses heuristic pattern matching to identify user preferences,
    personal information, and other memorable facts.
    """
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    new_memories: list[Memory] = []

    preference_indicators = [
        "my name is", "i am", "i like", "i love", "i use",
        "i work", "i prefer", "my favorite", "i'm using",
        "i have", "my email", "my phone", "i live", "i study",
        "i code", "i program", "i enjoy", "i hate", "i dislike",
        "i want", "i need", "i hope", "i wish", "i believe",
        "i think", "i feel", "my goal", "my project",
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
                sentences = content.replace("?", ".").replace("!", ".").split(".")
                for sentence in sentences:
                    if indicator in sentence.strip().lower():
                        candidate_text = sentence.strip().capitalize()

                        # Heuristic importance scoring
                        base_importance = 0.45
                        if any(k in candidate_text.lower() for k in ("prefer", "like", "love", "favorite", "enjoy")):
                            importance = min(0.95, base_importance + 0.25)
                        elif any(k in candidate_text.lower() for k in ("use", "work", "code", "program", "study")):
                            importance = min(0.9, base_importance + 0.15)
                        elif any(k in candidate_text.lower() for k in ("hate", "dislike")):
                            importance = min(0.85, base_importance + 0.2)
                        elif any(k in candidate_text.lower() for k in ("goal", "project", "want", "need")):
                            importance = min(0.9, base_importance + 0.3)
                        else:
                            importance = base_importance

                        if importance < 0.4:
                            break

                        # Determine memory type
                        mem_type = "Fact"
                        if any(k in candidate_text.lower() for k in ("prefer", "like", "love", "favorite", "enjoy", "hate", "dislike")):
                            mem_type = "Preference"
                        elif any(k in candidate_text.lower() for k in ("goal", "project", "want", "need")):
                            mem_type = "Goal"
                        elif any(k in candidate_text.lower() for k in ("work", "code", "program", "study")):
                            mem_type = "Fact"

                        # Save memory (with duplicate detection built-in)
                        memory = await save_memory(
                            session, uid, candidate_text,
                            source="conversation",
                            category=mem_type,
                            importance=importance,
                            memory_type=mem_type,
                            conversation_id=conversation_id,
                        )
                        new_memories.append(memory)
                        break
                break

    if new_memories:
        logger.info("Extracted %d memories from conversation", len(new_memories))

    return new_memories


# ──────────────────────────────────────────────
# Summarization
# ──────────────────────────────────────────────


async def summarize_conversation(
    session: AsyncSession,
    conversation_id: str | uuid.UUID,
    messages: list[dict[str, str]],
    *,
    user_id: str | uuid.UUID | None = None,
    save_as_memory: bool = False,
) -> str | None:
    """Generate a summary of a conversation.

    If save_as_memory is True and user_id is provided, the summary
    is also saved as a Memory entry for long-term recall.

    Creates an extractive summary with key topics and exchange count.
    """
    if len(messages) < 4:
        return None

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
        first_response = assistant_messages[0][:150] if assistant_messages else ""
        if first_response:
            summary += f" Assistant responded about: \"{first_response}\"."

    # Save summary as a memory entry if requested
    if save_as_memory and user_id is not None and summary:
        try:
            await save_memory(
                session,
                user_id,
                summary,
                source="conversation_summary",
                category="Summary",
                importance=0.6,
                memory_type="Summary",
                conversation_id=conversation_id,
            )
        except Exception:
            logger.exception("Failed to save conversation summary as memory")

    return summary
