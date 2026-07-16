"""Pydantic schemas for memory endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MemoryCreate(BaseModel):
    """Payload for creating a new memory."""

    content: str = Field(..., min_length=1, max_length=2000)
    source: str | None = Field(default=None, max_length=64)
    importance: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryUpdate(BaseModel):
    """Payload for updating an existing memory."""

    content: str | None = Field(default=None, min_length=1, max_length=2000)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)


class MemoryRead(BaseModel):
    """Schema returned when reading a memory."""

    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    source: str | None
    importance: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryListResponse(BaseModel):
    """Paginated memory list."""

    items: list[MemoryRead]
    total: int


class MemorySearchResponse(BaseModel):
    """Result from semantic memory search."""

    items: list[MemoryRead]
    query: str