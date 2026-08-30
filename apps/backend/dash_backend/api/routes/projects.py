"""REST API routes for project management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session

router = APIRouter(prefix="/projects", tags=["projects"])


# ──────────────────────────────────────────────
# In-memory project storage (simple dict-based until DB model is created)
# ──────────────────────────────────────────────

_projects_store: dict[str, dict] = {}
_next_id = 0


def _generate_id() -> str:
    global _next_id
    _next_id += 1
    return f"proj_{_next_id}"


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str = "active"
    created_at: str


@router.get("", response_model=List[ProjectRead])
async def list_projects(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> List[ProjectRead]:
    """List all projects for the current user."""
    user_projects = [
        p for p in _projects_store.values()
        if p.get("user_id") == str(user.id)
    ]
    return [
        ProjectRead(
            id=p["id"],
            name=p["name"],
            description=p.get("description"),
            status=p.get("status", "active"),
            created_at=p.get("created_at", ""),
        )
        for p in user_projects
    ]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    """Get a single project by id."""
    project = _projects_store.get(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if project.get("user_id") != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return ProjectRead(
        id=project["id"],
        name=project["name"],
        description=project.get("description"),
        status=project.get("status", "active"),
        created_at=project.get("created_at", ""),
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    """Create a new project."""
    project_id = _generate_id()
    now = datetime.now(UTC).isoformat()
    project = {
        "id": project_id,
        "user_id": str(user.id),
        "name": payload.name,
        "description": payload.description,
        "status": "active",
        "created_at": now,
    }
    _projects_store[project_id] = project
    return ProjectRead(
        id=project_id,
        name=payload.name,
        description=payload.description,
        status="active",
        created_at=now,
    )
