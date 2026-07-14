"""Interfaces for the dash_memory package.

This module contains only abstractions.
No backend and no vector database.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Iterable, Optional, Sequence

from dash_memory.types import MemoryRecord


class MemoryStore(ABC):
    """Persistence for memory records."""

    @abstractmethod
    def add(self, record: MemoryRecord) -> None:
        """Add a new memory record."""

    @abstractmethod
    def all(self) -> Sequence[MemoryRecord]:
        """Return all memory records."""

    @abstractmethod
    def filter(
        self,
        *,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
        created_after: Optional[datetime] = None,
        created_before: Optional[datetime] = None,
    ) -> Sequence[MemoryRecord]:
        """Return memory records matching the optional filters."""


class Retriever(ABC):
    """Select relevant memory records for a query."""

    @abstractmethod
    def retrieve(
        self,
        query: str,
        *,
        limit: int = 5,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Sequence[MemoryRecord]:
        """Retrieve the most relevant memory records for a query."""


class MemoryManager(ABC):
    """High-level API for ingesting and querying memories."""

    @abstractmethod
    def ingest(
        self,
        *,
        content: str,
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> MemoryRecord:
        """Add memory content and return the stored MemoryRecord."""

    @abstractmethod
    def query(
        self,
        query: str,
        *,
        limit: int = 5,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[Iterable[str]] = None,
    ) -> Sequence[MemoryRecord]:
        """Retrieve memories relevant to the query."""

