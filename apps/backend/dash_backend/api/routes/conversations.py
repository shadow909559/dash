"""REST API routes for conversation management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.api.schemas.conversation import (
    ConversationCreate,
    ConversationListRead,
    ConversationListResponse,
    ConversationRead,
    ConversationUpdate,
    MessageListResponse,
    MessageRead,
)
from dash_backend.auth.dependencies import get_current_user
from dash_backend.chat import service as chat_service
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session

router = APIRouter(prefix="/conversations", tags=["conversations"])


# ──────────────────────────────────────────────
# List conversations
# ──────────────────────────────────────────────


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    include_archived: bool = Query(default=False),
) -> ConversationListResponse:
    """List all active conversations for the current user."""
    conversations, total = await chat_service.get_user_conversations(
        session,
        user.id,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )

    items = [
        ConversationListRead.model_validate(c) for c in conversations
    ]

    has_more = (offset + limit) < total
    next_cursor = str(offset + limit) if has_more else None

    return ConversationListResponse(
        items=items,
        total=total,
        has_more=has_more,
        next_cursor=next_cursor,
    )


# ──────────────────────────────────────────────
# Search conversations
# ──────────────────────────────────────────────


@router.get("/search", response_model=list[ConversationListRead])
async def search_conversations(
    q: str = Query(..., min_length=1, max_length=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ConversationListRead]:
    """Search conversations by title."""
    conversations = await chat_service.search_conversations(
        session, user.id, query=q, limit=limit
    )
    return [ConversationListRead.model_validate(c) for c in conversations]


# ──────────────────────────────────────────────
# Create conversation
# ──────────────────────────────────────────────


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    """Create a new conversation."""
    conversation = await chat_service.create_conversation(
        session, user.id, title=payload.title, model=payload.model
    )
    return ConversationRead.model_validate(conversation)


# ──────────────────────────────────────────────
# Get conversation
# ──────────────────────────────────────────────


@router.get("/{conversation_id}", response_model=ConversationRead)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    """Get a single conversation by id."""
    conversation = await chat_service.get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")
    return ConversationRead.model_validate(conversation)


# ──────────────────────────────────────────────
# Update conversation
# ──────────────────────────────────────────────


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: uuid.UUID,
    payload: ConversationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRead:
    """Update conversation metadata (title, pin, favorite, archive)."""
    # Verify ownership
    conversation = await chat_service.get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")

    updated = await chat_service.update_conversation(
        session,
        conversation_id,
        title=payload.title,
        is_pinned=payload.is_pinned,
        is_favorited=payload.is_favorited,
        is_archived=payload.is_archived,
        model=payload.model,
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationRead.model_validate(updated)


# ──────────────────────────────────────────────
# Delete conversation
# ──────────────────────────────────────────────


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Permanently delete a conversation and all its messages."""
    conversation = await chat_service.get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")

    deleted = await chat_service.delete_conversation(session, conversation_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


# ──────────────────────────────────────────────
# Get conversation messages
# ──────────────────────────────────────────────


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    before_id: uuid.UUID | None = Query(default=None),
) -> MessageListResponse:
    """Get paginated messages for a conversation (oldest first)."""
    conversation = await chat_service.get_conversation(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your conversation")

    messages, total = await chat_service.get_conversation_messages(
        session,
        conversation_id,
        limit=limit,
        offset=offset,
        before_id=before_id,
    )

    items = [MessageRead.model_validate(m) for m in messages]

    has_more = (offset + limit) < total
    next_cursor = str(messages[0].id) if has_more and messages else None

    return MessageListResponse(
        items=items,
        total=total,
        has_more=has_more,
        next_cursor=next_cursor,
    )