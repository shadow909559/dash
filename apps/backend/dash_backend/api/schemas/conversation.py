"""Pydantic schemas for conversation endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Conversation
# ──────────────────────────────────────────────


class ConversationCreate(BaseModel):
    """Payload for creating a new conversation."""

    title: str | None = Field(default=None, max_length=255)
    model: str | None = None


class ConversationUpdate(BaseModel):
    """Payload for updating conversation metadata."""

    title: str | None = Field(default=None, max_length=255)
    is_pinned: bool | None = None
    is_favorited: bool | None = None
    is_archived: bool | None = None
    model: str | None = None


class ConversationRead(BaseModel):
    """Schema returned to clients when reading a conversation."""

    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None
    is_pinned: bool
    is_favorited: bool
    is_archived: bool
    archived_at: datetime | None
    summary: str | None
    summary_updated_at: datetime | None
    message_count: int
    token_count: int
    last_message_at: datetime | None
    model: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListRead(BaseModel):
    """Lightweight schema for listing conversations (excludes full summary)."""

    id: uuid.UUID
    title: str | None
    is_pinned: bool
    is_favorited: bool
    is_archived: bool
    message_count: int
    last_message_at: datetime | None
    model: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# Messages
# ──────────────────────────────────────────────


class MessageRead(BaseModel):
    """Schema returned when reading a message."""

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    token_count: int | None
    model: str | None
    meta: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageListResponse(BaseModel):
    """Paginated message list."""

    items: list[MessageRead]
    total: int
    has_more: bool
    next_cursor: str | None


# ──────────────────────────────────────────────
# Conversation List (paginated)
# ──────────────────────────────────────────────


class ConversationListResponse(BaseModel):
    """Paginated conversation list."""

    items: list[ConversationListRead]
    total: int
    has_more: bool
    next_cursor: str | None