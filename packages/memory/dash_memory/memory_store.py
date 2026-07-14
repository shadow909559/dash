"""Memory store implementations.

No backend. No vector database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence
from uuid import uuid4

from dash_memory.interfaces import MemoryStore
from dash_memory.types import MemoryRecord


class InMemoryMemoryStore(MemoryStore):
    """Simple in-memory memory store."""

    def __init__(self) -> None:
        self._records: List[MemoryRecord] = []

    def add(self, record: MemoryRecord) -> None:
        # In-memory store: just append.
        self._records.append(record)

    def all(self) -> Sequence[MemoryRecord]:
        return list(self._records)

    def filter(
        self,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ) -> Sequence[MemoryRecord]:
        # Current MemoryRecord scaffold does not include user/session/tags.
        # We therefore implement filters as no-ops except for timestamps.
        result: List[MemoryRecord] = []
        for r in self._records:
            if created_after is not None and r.created_at < created_after:
                continue
            if created_before is not None and r.created_at > created_before:
                continue
            result.append(r)
        return result


def default_memory_store() -> InMemoryMemoryStore:
    return InMemoryMemoryStore()

