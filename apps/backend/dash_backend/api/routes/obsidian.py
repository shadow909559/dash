"""Obsidian vault integration API routes.

Provides CRUD operations for the configured Obsidian vault.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user
from dash_backend.logging_config import get_logger
from dash_backend.services.obsidian import get_obsidian_service

logger = get_logger(__name__)

router = APIRouter(prefix="/obsidian", tags=["obsidian"], dependencies=[Depends(get_current_user)])


class NoteCreateRequest(BaseModel):
    path: str = Field(..., description="Relative path within the vault")
    content: str = Field(default="", description="Markdown content")
    frontmatter: dict[str, Any] | None = None


class NoteUpdateRequest(BaseModel):
    content: str = Field(..., description="New Markdown content")


class NoteAppendRequest(BaseModel):
    content: str = Field(..., description="Content to append")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")


# ── Health ─────────────────────────────────────────────────

@router.get("/health")
async def obsidian_health() -> dict[str, Any]:
    """Check Obsidian vault health."""
    svc = get_obsidian_service()
    return await svc.health_check()


# ── List ───────────────────────────────────────────────────

@router.get("/list")
async def list_notes(folder: Optional[str] = None) -> dict[str, Any]:
    """List all notes in the vault."""
    svc = get_obsidian_service()
    notes = await svc.list_notes(folder)
    return {"notes": notes, "count": len(notes)}


# ── Search ─────────────────────────────────────────────────

@router.post("/search")
async def search_notes(req: SearchRequest) -> dict[str, Any]:
    """Search vault notes by text."""
    svc = get_obsidian_service()
    results = await svc.search_notes(req.query)
    return {"results": results, "count": len(results)}


# ── Read ───────────────────────────────────────────────────

@router.get("/read")
async def read_note(path: str) -> dict[str, Any]:
    """Read a note's content."""
    svc = get_obsidian_service()
    try:
        return await svc.read_note(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Create ─────────────────────────────────────────────────

@router.post("/create")
async def create_note(req: NoteCreateRequest) -> dict[str, Any]:
    """Create a new note."""
    svc = get_obsidian_service()
    return await svc.create_note(req.path, req.content, req.frontmatter)


# ── Update ─────────────────────────────────────────────────

@router.put("/update")
async def update_note(path: str, req: NoteUpdateRequest) -> dict[str, Any]:
    """Update an existing note."""
    svc = get_obsidian_service()
    try:
        return await svc.update_note(path, req.content)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Delete ─────────────────────────────────────────────────

@router.delete("/delete")
async def delete_note(path: str) -> dict[str, Any]:
    """Delete a note."""
    svc = get_obsidian_service()
    try:
        return await svc.delete_note(path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Append ─────────────────────────────────────────────────

@router.post("/append")
async def append_note(path: str, req: NoteAppendRequest) -> dict[str, Any]:
    """Append content to an existing note."""
    svc = get_obsidian_service()
    try:
        return await svc.append_note(path, req.content)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Wiki-links ─────────────────────────────────────────────

@router.get("/links")
async def get_links(path: str) -> dict[str, Any]:
    """Get wiki-links from a note."""
    svc = get_obsidian_service()
    links = await svc.get_note_links(path)
    return {"links": links, "count": len(links)}


# ── Project note ───────────────────────────────────────────

@router.post("/project")
async def create_project_note(project_name: str, content: str = "") -> dict[str, Any]:
    """Create a note in the Projects folder."""
    svc = get_obsidian_service()
    return await svc.create_project_note(project_name, content)


# ── Daily note ─────────────────────────────────────────────

@router.post("/daily")
async def create_daily_note(content: str = "") -> dict[str, Any]:
    """Create a daily note."""
    svc = get_obsidian_service()
    return await svc.create_daily_note(content)
