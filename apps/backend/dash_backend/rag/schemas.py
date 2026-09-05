"""Pydantic schemas for RAG endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentCreate(BaseModel):
    filename: str | None = Field(default=None, max_length=255)
    content: str = Field(..., min_length=1)
    metadata: dict[str, Any] | None = None


class DocumentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    filename: str | None
    content: str
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_text: str
    chunk_index: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResultItem(BaseModel):
    document_id: uuid.UUID
    filename: str | None
    chunk_index: int
    chunk_text: str
    score: float | None = None


class SearchResponse(BaseModel):
    items: list[SearchResultItem]
    query: str

