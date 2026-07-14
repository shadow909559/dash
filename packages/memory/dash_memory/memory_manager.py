"""Memory manager.

No backend.
No vector database.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence
from uuid import uuid4

from dash_memory.interfaces import MemoryManager, MemoryStore, Retriever
from dash_memory.types import MemoryRecord


class DefaultMemoryManager(MemoryManager):
    """Ingest and query memories using injected store and retriever."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        retriever: Retriever,
    ) -> None:
        self._store = store
        self._retriever = retriever

    def ingest(
        self,
        *,
        content: str,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> MemoryRecord:
        # MemoryRecord scaffold only supports id/content/created_at.
        _ = (user_id, session_id, tags)
        record = MemoryRecord(id=record_id or str(uuid4()), content=content)
        self._store.add(record)
        return record

    def query(
        self,
        query: str,
        *,
        limit: int = 5,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Sequence[MemoryRecord]:
        return self._retriever.retrieve(
            query,
            limit=limit,
            user_id=user_id,
            session_id=session_id,
            tags=tags,
        )

