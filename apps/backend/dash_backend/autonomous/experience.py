"""Experience Cache — remembers what worked so the agent learns from past goals.

When a goal completes successfully, the agent stores:
  - The goal description
  - The sequence of tools that worked (tool_name + args + result summary)
  - The final outcome

When a new goal starts, the agent retrieves similar past experiences
and injects them into the thinking context. This way, if the agent
successfully searched Downloads before, it remembers the exact path
and tool to use next time.

This is the difference between a chatbot and an agent that learns.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GoalExperience:
    """A recorded experience from a completed goal."""
    goal_description: str
    tool_sequence: list[dict[str, Any]]  # [{tool, args, result_summary, success}]
    outcome: str  # final result or error
    success: bool
    timestamp: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    embedding: list[float] | None = None  # 768-dim vector for semantic matching
    tags: list[str] = field(default_factory=list)  # extracted keywords

    def to_dict(self) -> dict:
        return {
            "goal": self.goal_description[:100],
            "tools": [t["tool"] for t in self.tool_sequence if t.get("success")],
            "outcome": self.outcome[:100],
            "success": self.success,
            "age_hours": round((time.time() - self.timestamp) / 3600, 1),
            "access_count": self.access_count,
        }

    def tool_summary(self) -> str:
        """Human-readable summary of what tools were used successfully."""
        successful = [t for t in self.tool_sequence if t.get("success")]
        if not successful:
            return "No successful steps recorded."
        lines = []
        for t in successful:
            args_str = json.dumps(t.get("args", {}))[:80]
            lines.append(f"  - {t['tool']}({args_str}) → {(t.get('result_summary', '') or '')[:60]}")
        return "\n".join(lines)


class ExperienceCache:
    """In-memory cache of past goal experiences.

    Stores successful goal patterns and retrieves similar ones
    for injection into new goal contexts.

    Features:
    - Embedding-based semantic matching (nomic-embed-text)
    - Time decay: older experiences score lower
    - Cross-session persistence via memories table
    """

    DECAY_HALF_LIFE_HOURS = 168.0  # 7 days — halving time for experience relevance

    def __init__(self, max_entries: int = 50):
        self._experiences: list[GoalExperience] = []
        self._max_entries = max_entries
        self._loaded = False

    def record(self, goal_description: str, steps: list[Any], outcome: str, success: bool) -> None:
        """Record a completed goal's experience."""
        tool_sequence = []
        for s in steps:
            if hasattr(s, "tool_name") and s.tool_name:
                tool_sequence.append({
                    "tool": s.tool_name,
                    "args": getattr(s, "tool_args", {}) or {},
                    "result_summary": (getattr(s, "tool_result", None) or "")[:200],
                    "success": getattr(s, "success", False),
                })

        if not tool_sequence:
            return  # nothing useful to remember

        tags = _extract_tags(goal_description)

        exp = GoalExperience(
            goal_description=goal_description,
            tool_sequence=tool_sequence,
            outcome=outcome[:500],
            success=success,
            tags=tags,
        )

        self._experiences.append(exp)

        # Keep bounded
        if len(self._experiences) > self._max_entries:
            self._experiences = self._experiences[-self._max_entries:]

        # Generate embedding asynchronously (fire and forget)
        asyncio.create_task(self._generate_exp_embedding(exp))

        # Persist to database
        asyncio.create_task(self._persist_experience(exp))

        logger.info(
            "Experience recorded: '%s' → %d tools, success=%s",
            goal_description[:50], len(tool_sequence), success,
        )

    async def _generate_exp_embedding(self, exp: GoalExperience) -> None:
        """Generate embedding for a recorded experience."""
        try:
            from dash_backend.intelligence.memory_service import MemoryService
            svc = MemoryService()
            exp.embedding = await svc._generate_embedding(exp.goal_description)
        except Exception:
            pass

    async def _persist_experience(self, exp: GoalExperience) -> None:
        """Save experience to the memories table for cross-session persistence."""
        try:
            import uuid
            from dash_backend.db.session import AsyncSessionLocal
            from dash_backend.intelligence.memory_service import MemoryService

            content = json.dumps(exp.to_dict())
            importance = 0.7 if exp.success else 0.3

            svc = MemoryService()
            async with AsyncSessionLocal() as session:
                # Use a fixed user ID for autonomous agent experiences
                uid = uuid.UUID("00000000-0000-0000-0000-000000000001")
                await svc.store_long_term(
                    session, uid, content,
                    memory_type="experience",
                    importance=importance,
                )
        except Exception:
            pass

    async def load_from_db(self) -> int:
        """Load persisted experiences from the memories table."""
        if self._loaded:
            return 0
        self._loaded = True

        try:
            import uuid
            from dash_backend.db.session import AsyncSessionLocal
            from dash_backend.intelligence.memory_service import MemoryService

            svc = MemoryService()
            async with AsyncSessionLocal() as session:
                uid = uuid.UUID("00000000-0000-0000-0000-000000000001")
                memories, _ = await svc.get_user_memories(
                    session, uid, limit=self._max_entries, memory_type="experience"
                )

                loaded = 0
                for mem in memories:
                    try:
                        data = json.loads(mem.content)
                        exp = GoalExperience(
                            goal_description=data.get("goal", ""),
                            tool_sequence=[],  # tools not stored in to_dict
                            outcome=data.get("outcome", ""),
                            success=data.get("success", False),
                            timestamp=mem.created_at.timestamp() if mem.created_at else time.time(),
                        )
                        self._experiences.append(exp)
                        loaded += 1
                    except Exception:
                        continue

                logger.info("Loaded %d experiences from database", loaded)
                return loaded
        except Exception:
            return 0

    async def retrieve(self, goal_description: str, top_k: int = 3) -> list[GoalExperience]:
        """Find past experiences similar to the given goal.

        Uses embedding cosine similarity when available, falls back to
        keyword overlap. Applies time decay so recent experiences rank higher.
        """
        if not self._experiences:
            return []

        # Try embedding-based matching first
        scored = await self._score_by_embedding(goal_description)

        # Fall back to keyword overlap if embeddings unavailable
        if not scored:
            scored = self._score_by_keywords(goal_description)

        if not scored:
            return []

        # Apply time decay
        now = time.time()
        decayed = []
        for score, exp in scored:
            age_hours = (now - exp.timestamp) / 3600
            decay = 0.5 ** (age_hours / self.DECAY_HALF_LIFE_HOURS)
            # Successful experiences get a bonus
            success_bonus = 1.2 if exp.success else 0.8
            final_score = score * decay * success_bonus
            decayed.append((final_score, exp))

        decayed.sort(key=lambda x: x[0], reverse=True)

        # Mark as accessed
        for _, exp in decayed[:top_k]:
            exp.last_accessed = time.time()
            exp.access_count += 1

        return [exp for _, exp in decayed[:top_k]]

    async def _score_by_embedding(self, goal_description: str) -> list[tuple[float, GoalExperience]]:
        """Score experiences by cosine similarity of embeddings."""
        try:
            from dash_backend.intelligence.memory_service import MemoryService
            svc = MemoryService()
            query_emb = await svc._generate_embedding(goal_description)

            if not query_emb or not any(query_emb):
                return []

            scored = []
            for exp in self._experiences:
                if exp.embedding and any(exp.embedding):
                    sim = _cosine_similarity(query_emb, exp.embedding)
                    if sim > 0.3:  # minimum similarity threshold
                        scored.append((sim, exp))

            return scored
        except Exception:
            return []

    def _score_by_keywords(self, goal_description: str) -> list[tuple[float, GoalExperience]]:
        """Score experiences by keyword overlap (fast fallback)."""
        goal_tags = _extract_tags(goal_description)
        if not goal_tags:
            return []

        scored = []
        for exp in self._experiences:
            overlap = len(goal_tags & set(exp.tags))
            if overlap > 0:
                scored.append((overlap, exp))
        return scored

    async def format_for_context(self, goal_description: str) -> str:
        """Retrieve and format past experiences for injection into the agent prompt."""
        experiences = await self.retrieve(goal_description)
        if not experiences:
            return ""

        lines = ["PAST EXPERIENCES (similar goals that worked before):"]
        for i, exp in enumerate(experiences, 1):
            lines.append(f"\n{i}. Goal: \"{exp.goal_description[:80]}\"")
            lines.append(f"   Tools used successfully:")
            lines.append(exp.tool_summary())
            lines.append(f"   Outcome: {exp.outcome[:80]}")

        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {
            "total": len(self._experiences),
            "successful": sum(1 for e in self._experiences if e.success),
            "failed": sum(1 for e in self._experiences if not e.success),
        }


def _extract_tags(text: str) -> set[str]:
    """Extract meaningful keywords from text for matching."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "all", "each", "every", "both", "few", "more", "most", "other",
        "some", "such", "no", "nor", "not", "only", "own", "same", "so",
        "than", "too", "very", "just", "because", "but", "and", "or", "if",
        "while", "about", "against", "up", "down", "find", "list", "get",
        "show", "check", "look", "see", "make", "create", "set", "run",
        "and", "that", "this", "it", "my", "your", "me", "i",
    }
    words = set()
    for word in text.lower().split():
        clean = "".join(c for c in word if c.isalnum())
        if len(clean) > 2 and clean not in stop_words:
            words.add(clean)
    return words


# Singleton
_cache: ExperienceCache | None = None


def get_experience_cache() -> ExperienceCache:
    global _cache
    if _cache is None:
        _cache = ExperienceCache()
    return _cache
