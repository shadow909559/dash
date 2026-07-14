"""Retrieval logic for memory records.

This module uses basic token overlap scoring.
No vector database.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Optional, Sequence

from dash_memory.interfaces import Retriever
from dash_memory.types import MemoryRecord


def _normalize(text: str) -> list[str]:
    return [t.strip().lower() for t in text.split() if t.strip()]


class SimpleTokenOverlapRetriever(Retriever):
    """Retriever based on token overlap."""

    def __init__(self, *, store) -> None:
        self._store = store

    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Sequence[MemoryRecord]:
        records = self._store.filter(
            user_id=user_id,
            session_id=session_id,
            tags=tags,
        )

        query_tokens = _normalize(query)
        if not query_tokens:
            return sorted(records, key=lambda r: r.created_at, reverse=True)[:limit]

        query_counter = Counter(query_tokens)

        def score(rec: MemoryRecord) -> int:
            mem_tokens = _normalize(rec.content)
            mem_counter = Counter(mem_tokens)
            return sum(
                min(query_counter[t], mem_counter[t]) for t in query_counter.keys()
            )

        ranked = sorted(records, key=lambda r: (score(r), r.created_at), reverse=True)
        positive = [r for r in ranked if score(r) > 0]
        result = positive if positive else ranked
        return result[:limit]

