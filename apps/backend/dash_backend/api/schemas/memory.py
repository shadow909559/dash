"""Pydantic schemas for memory endpoints."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


def _sanitize_text(v: str) -> str:
    """Strip HTML tags and script injection from user input."""
    v = re.sub(r'<script[^>]*>.*?</script>', '', v, flags=re.DOTALL | re.IGNORECASE)
    v = re.sub(r'<[^>]+>', '', v)
    v = v.strip()
    return v


class MemoryCreate(BaseModel):
    """Payload for creating a new memory."""

    content: str = Field(..., min_length=1, max_length=2000)
    type: str = Field(default="fact", max_length=32)
    source: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    importance: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    project_id: uuid.UUID | None = Field(default=None)

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return _sanitize_text(v)


class MemoryUpdate(BaseModel):
    """Payload for updating an existing memory."""

    content: str | None = Field(default=None, min_length=1, max_length=2000)
    type: str | None = Field(default=None, max_length=32)
    source: str | None = Field(default=None, max_length=64)
    category: str | None = Field(default=None, max_length=64)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    project_id: uuid.UUID | None = Field(default=None)


class MemoryRead(BaseModel):
    """Schema returned when reading a memory."""

    id: uuid.UUID
    user_id: uuid.UUID
    content: str
    type: str
    source: str | None
    category: str | None
    importance: float
    confidence: float
    project_id: uuid.UUID | None
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


# ── Typed Memory (Part 9-10) ────────────────────────────────────────


class TypedMemoryCreate(BaseModel):
    """Payload for creating a typed memory (personal/preference/project/decision/experience)."""

    content: str = Field(..., min_length=1, max_length=2000)
    memory_type: str = Field(..., description="One of: personal, preference, project, decision, experience")
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str | None = Field(default=None, max_length=64)
    project_id: uuid.UUID | None = Field(default=None)
    title: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = Field(default=None)

    @field_validator('content')
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        return _sanitize_text(v)


class DecisionCreate(BaseModel):
    """Payload for the 'remember this decision' flow."""

    decision: str = Field(..., min_length=1, max_length=2000)
    rationale: str = Field(default="", max_length=2000)
    alternatives: list[str] | None = Field(default=None)
    project_id: uuid.UUID | None = Field(default=None)
    importance: float = Field(default=0.7, ge=0.0, le=1.0)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)

    @field_validator('decision', 'rationale')
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _sanitize_text(v)


class WorkContextCreate(BaseModel):
    """Payload for the 'continue where we left off' flow."""

    task: str = Field(..., min_length=1, max_length=1000)
    progress: str = Field(default="", max_length=2000)
    blockers: list[str] | None = Field(default=None)
    next_steps: list[str] | None = Field(default=None)
    project_id: uuid.UUID | None = Field(default=None)


class MemoryStatsResponse(BaseModel):
    """Aggregate memory statistics."""

    total: int
    by_type: dict[str, int]
    avg_importance: float
    avg_confidence: float
    project_count: int
