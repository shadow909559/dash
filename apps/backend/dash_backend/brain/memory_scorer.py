"""Memory Scorer - Scores and ranks memories for retrieval.

Provides intelligent memory scoring based on relevance,
recency, importance, and user context.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class MemoryScorer:
    """Scores memories using multiple signals for optimal retrieval.

    Scoring factors:
    - Semantic relevance (via embedding similarity when available)
    - Recency (exponential decay)
    - Importance (user-defined or inferred)
    - Access frequency
    - Contextual relevance (based on current query/task)
    - Category matching
    - Memory type matching
    """

    # Scoring weights
    WEIGHT_SEMANTIC = 0.35
    WEIGHT_RECENCY = 0.20
    WEIGHT_IMPORTANCE = 0.25
    WEIGHT_FREQUENCY = 0.10
    WEIGHT_CONTEXTUAL = 0.10

    RECENCY_HALF_LIFE_DAYS = 14.0
    FREQUENCY_MAX = 50

    @staticmethod
    def score_memory(
        memory: Dict[str, Any],
        query: Optional[str] = None,
        context_category: Optional[str] = None,
    ) -> float:
        """Compute a composite score for a memory.

        Args:
            memory: Memory dict with content, importance, created_at, etc.
            query: Optional search query for relevance scoring
            context_category: Optional category context for boosting

        Returns:
            Float score between 0 and 1
        """
        scores = []
        weights = []

        # Semantic relevance
        semantic_score = MemoryScorer._compute_semantic_relevance(
            memory.get("content", ""),
            query or "",
        )
        scores.append(semantic_score)
        weights.append(MemoryScorer.WEIGHT_SEMANTIC)

        # Importance
        importance = memory.get("importance", 0.5)
        scores.append(min(1.0, importance))
        weights.append(MemoryScorer.WEIGHT_IMPORTANCE)

        # Recency
        recency = MemoryScorer._compute_recency(memory.get("created_at", ""))
        scores.append(recency)
        weights.append(MemoryScorer.WEIGHT_RECENCY)

        # Frequency
        access_count = memory.get("access_count", 0) or 0
        frequency = min(access_count, MemoryScorer.FREQUENCY_MAX) / MemoryScorer.FREQUENCY_MAX
        scores.append(frequency)
        weights.append(MemoryScorer.WEIGHT_FREQUENCY)

        # Contextual relevance
        contextual = MemoryScorer._compute_contextual_relevance(
            memory,
            context_category,
        )
        scores.append(contextual)
        weights.append(MemoryScorer.WEIGHT_CONTEXTUAL)

        # Weighted average
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
        return max(0.0, min(1.0, weighted_score))

    @staticmethod
    def rank_memories(
        memories: List[Dict[str, Any]],
        query: Optional[str] = None,
        context_category: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Rank memories by composite score.

        Args:
            memories: List of memory dicts
            query: Optional search query
            context_category: Optional category context
            top_k: Number of top memories to return

        Returns:
            Ranked list of memory dicts with score added
        """
        scored = []
        for memory in memories:
            score = MemoryScorer.score_memory(
                memory, query=query, context_category=context_category
            )
            scored.append((score, memory))

        scored.sort(key=lambda x: x[0], reverse=True)
        result = []
        for score, memory in scored[:top_k]:
            memory["_score"] = score
            result.append(memory)

        return result

    @staticmethod
    def _compute_semantic_relevance(
        content: str,
        query: str,
    ) -> float:
        """Compute semantic relevance between content and query."""
        if not query or not content:
            return 0.0

        content_lower = content.lower()
        query_lower = query.lower()

        # Simple keyword overlap scoring
        query_words = set(query_lower.split())
        content_words = set(content_lower.split())

        if not query_words:
            return 0.0

        intersection = query_words & content_words
        if not intersection:
            return 0.0

        # Jaccard similarity
        jaccard = len(intersection) / len(query_words | content_words)

        # Phrase matching bonus
        phrase_bonus = 0.0
        if query_lower in content_lower:
            phrase_bonus = 0.3

        # Word order proximity bonus
        order_score = 0.0
        query_terms = list(query_words)
        if len(query_terms) >= 2:
            positions = []
            for term in query_terms:
                try:
                    pos = content_lower.index(term)
                    positions.append(pos)
                except ValueError:
                    pass
            if len(positions) >= 2:
                avg_gap = max(
                    abs(positions[i] - positions[i - 1])
                    for i in range(1, len(positions))
                )
                order_score = max(0, 1.0 - (avg_gap / len(content_lower)))

        return min(1.0, jaccard + phrase_bonus + order_score * 0.2)

    @staticmethod
    def _compute_recency(created_at_str: str) -> float:
        """Compute recency score using exponential decay."""
        if not created_at_str:
            return 0.5  # Default mid-range

        try:
            if isinstance(created_at_str, str):
                created = datetime.fromisoformat(created_at_str)
            else:
                created = created_at_str

            now = datetime.now(timezone.utc)
            age_days = max(0.0, (now - created).total_seconds() / 86400.0)
            return math.exp(-age_days / MemoryScorer.RECENCY_HALF_LIFE_DAYS)
        except (ValueError, TypeError):
            return 0.5

    @staticmethod
    def _compute_contextual_relevance(
        memory: Dict[str, Any],
        context_category: Optional[str],
    ) -> float:
        """Compute contextual relevance based on category matching."""
        if not context_category:
            return 0.0

        mem_category = memory.get("category", "")
        mem_type = memory.get("type", "")

        if not mem_category and not mem_type:
            return 0.0

        context_lower = context_category.lower()

        # Exact match
        if mem_category.lower() == context_lower:
            return 1.0
        if mem_type.lower() == context_lower:
            return 0.9

        # Partial match
        if context_lower in mem_category.lower() or context_lower in mem_type.lower():
            return 0.6

        return 0.0