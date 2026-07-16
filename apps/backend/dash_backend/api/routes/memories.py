"""REST API routes for memory management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.api.schemas.memory import (
    MemoryCreate,
    MemoryListResponse,
    MemoryRead,
    MemorySearchResponse,
    MemoryUpdate,
)
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.memory import service as memory_service

router = APIRouter(prefix="/memories", tags=["memories"])


# ──────────────────────────────────────────────
# List memories
# ──────────────────────────────────────────────


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    min_importance: float = Query(default=0.0, ge=0.0, le=1.0),
    category: str | None = Query(default=None, max_length=64),
) -> MemoryListResponse:

    """List all memories for the current user, ordered by importance."""
    memories, total = await memory_service.get_user_memories(
        session,
        user.id,
        limit=limit,
        offset=offset,
        min_importance=min_importance,
        category=category,
    )

    items = [MemoryRead.model_validate(m) for m in memories]


    return MemoryListResponse(items=items, total=total)


# ──────────────────────────────────────────────
# Create memory
# ──────────────────────────────────────────────


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def create_memory(
    payload: MemoryCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRead:
    """Store a new memory."""
    memory = await memory_service.save_memory(
        session,
        user.id,
        content=payload.content,
        source=payload.source,
        category=payload.category,
        importance=payload.importance,
    )

    return MemoryRead.model_validate(memory)


# ──────────────────────────────────────────────
# Get memory
# ──────────────────────────────────────────────


@router.get("/{memory_id}", response_model=MemoryRead)
async def get_memory(
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRead:
    """Get a single memory by id."""
    memory = await memory_service.retrieve_memory(session, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if memory.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your memory")
    return MemoryRead.model_validate(memory)


# ──────────────────────────────────────────────
# Update memory
# ──────────────────────────────────────────────


@router.patch("/{memory_id}", response_model=MemoryRead)
async def update_memory(
    memory_id: uuid.UUID,
    payload: MemoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MemoryRead:
    """Update memory content or importance."""
    memory = await memory_service.retrieve_memory(session, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if memory.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your memory")

    updated = await memory_service.update_memory(
        session,
        memory_id,
        content=payload.content,
        source=payload.source,
        category=payload.category,
        importance=payload.importance,
    )

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return MemoryRead.model_validate(updated)


# ──────────────────────────────────────────────
# Delete memory
# ──────────────────────────────────────────────


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Permanently delete a memory."""
    memory = await memory_service.retrieve_memory(session, memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    if memory.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your memory")

    deleted = await memory_service.delete_memory(session, memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")