"""Personal assistant helpers (Phase 11).

Provides a small personal profile system and daily summary endpoints that reuse
existing memory and RAG services. Kept intentionally small and non-invasive: data
is stored in the existing memories table using category tags so we avoid new
persistent tables.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.session import get_db_session
from dash_backend.memory import service as memory_service
from dash_backend.rag import service as rag_service
from dash_backend.api.schemas.memory import MemoryRead as MemoryReadSchema
from pydantic import BaseModel

router = APIRouter()


class ProfileIn(BaseModel):
    preferences: Optional[Dict[str, Any]] = None
    working_style: Optional[str] = None
    common_tasks: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    device_info: Optional[Dict[str, Any]] = None
    project_context: Optional[Dict[str, Any]] = None


class ProfileOut(ProfileIn):
    pass


class ItemOut(BaseModel):
    id: str
    content: str
    category: Optional[str]
    importance: float
    source: Optional[str]


# --- Profile helpers ---

async def _get_profile_memory(session: AsyncSession, user_id: str):
    # find latest memory with category 'profile' and source 'personal_profile'
    mems, _ = await memory_service.get_user_memories(session, user_id, limit=1, category="profile")
    if mems:
        # prefer source personal_profile
        for m in mems:
            if getattr(m, "source", None) == "personal_profile":
                return m
        return mems[0]
    return None


@router.get("/profile", response_model=ProfileOut)
async def get_profile(user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """Return the user's structured profile stored as a memory (category='profile')."""
    m = await _get_profile_memory(session, user.id)
    if m is None:
        return ProfileOut()
    try:
        payload = json.loads(m.content)
    except Exception:
        # legacy plain text profile; return as a text preference
        return ProfileOut(preferences={"bio": m.content})
    return ProfileOut(**payload)


@router.post("/profile", response_model=ProfileOut)
async def upsert_profile(payload: ProfileIn, user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """Create or update the user's profile. Stored as a single memory item.

    This deliberately reuses the memories table to avoid additional persistent
    schema. The content field stores JSON.
    """
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No profile data provided")

    existing = await _get_profile_memory(session, user.id)
    if existing:
        # update content and bump importance
        updated = await memory_service.update_memory(session, existing.id, content=json.dumps(data), importance=0.95)
        try:
            out = ProfileOut(**data)
        except Exception:
            out = ProfileOut()
        return out

    mem = await memory_service.save_memory(session, user.id, json.dumps(data), source="personal_profile", category="profile", importance=0.95)
    try:
        out = ProfileOut(**data)
    except Exception:
        out = ProfileOut()
    return out


# --- Simple task/reminder/note endpoints (backed by memories) ---

@router.post("/items", response_model=ItemOut)
async def create_item(
    category: str,
    content: str,
    importance: float = 0.5,
    user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a simple personal item (category examples: task, reminder, note).

    Items are stored as memories with the provided category so they are
    searchable and included in profile/summary flows.
    """
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="category is required")
    mem = await memory_service.save_memory(session, user.id, content=content, source="personal_item", category=category, importance=importance)
    return ItemOut(id=str(mem.id), content=mem.content, category=mem.category, importance=mem.importance or 0.0, source=mem.source)


@router.get("/items", response_model=List[ItemOut])
async def list_items(category: Optional[str] = None, user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """List personal items filtered by category (if provided)."""
    mems, _ = await memory_service.get_user_memories(session, user.id, limit=200, category=category)
    out: List[ItemOut] = []
    for m in mems:
        out.append(ItemOut(id=str(m.id), content=m.content, category=m.category, importance=m.importance or 0.0, source=m.source))
    return out


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """Delete a personal item (memory). Users may only delete their own items."""
    mem = await memory_service.retrieve_memory(session, item_id)
    if mem is None or str(mem.user_id) != str(user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    ok = await memory_service.delete_memory(session, item_id)
    return {"deleted": ok}


# --- Daily summary ---

@router.get("/summary", response_model=Dict[str, Any])
async def daily_summary(user=Depends(get_current_user), session: AsyncSession = Depends(get_db_session), rag_query: Optional[str] = None):
    """Produce a short daily summary composed from memories and RAG documents.

    - memory_context: the top memories (preferences, tasks, reminders)
    - rag_context: top document chunks relevant to rag_query (or recent docs)
    - tasks/reminders/notes lists
    """
    mem_context = await memory_service.build_memory_context(session, user.id, max_memories=20, min_importance=0.2)
    rag_ctx = await rag_service.retrieve_context(session, user.id, query=rag_query, max_chunks=6)

    tasks_raw, _ = await memory_service.get_user_memories(session, user.id, limit=200, category="task")
    reminders_raw, _ = await memory_service.get_user_memories(session, user.id, limit=200, category="reminder")
    notes_raw, _ = await memory_service.get_user_memories(session, user.id, limit=200, category="note")

    def to_item(m):
        return {
            "id": str(m.id),
            "content": m.content,
            "category": m.category,
            "importance": m.importance or 0.0,
            "source": m.source,
        }

    return {
        "memory_context": mem_context,
        "rag_context": rag_ctx,
        "tasks": [to_item(m) for m in tasks_raw],
        "reminders": [to_item(m) for m in reminders_raw],
        "notes": [to_item(m) for m in notes_raw],
    }
