"""FastAPI router for automation endpoints."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.automation import schemas
from dash_backend.automation import service as automation_service
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.session import get_db_session
from dash_backend.db.models.user import User

router = APIRouter(prefix="", tags=["automation"])


@router.post("/automation", response_model=schemas.AutomationRead, status_code=status.HTTP_201_CREATED)
async def create_automation(
    payload: schemas.AutomationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.AutomationRead:
    auto = await automation_service.create_automation(
        session,
        user.id,
        payload.name,
        payload.description,
        payload.trigger_type,
        payload.schedule,
        payload.tool_name,
        payload.tool_arguments,
        enabled=payload.enabled,
    )
    return schemas.AutomationRead.model_validate(auto)


@router.get("/automation", response_model=List[schemas.AutomationRead])
async def list_automations(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> List[schemas.AutomationRead]:
    autos = await automation_service.list_automations(session, user.id)
    return [schemas.AutomationRead.model_validate(a) for a in autos]


@router.patch("/automation/{automation_id}", response_model=schemas.AutomationRead)
async def patch_automation(
    automation_id: uuid.UUID,
    payload: schemas.AutomationUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.AutomationRead:
    a = await automation_service.get_automation(session, automation_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
    if a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your automation")
    updated = await automation_service.update_automation(session, automation_id, **payload.model_dump(exclude_none=True))
    return schemas.AutomationRead.model_validate(updated)


@router.delete("/automation/{automation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation(
    automation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    a = await automation_service.get_automation(session, automation_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
    if a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your automation")
    await automation_service.delete_automation(session, automation_id)
    return None


@router.get("/automation/{automation_id}/history", response_model=List[schemas.AutomationExecutionRead])
async def get_automation_history(
    automation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    limit: int = 50,
) -> List[schemas.AutomationExecutionRead]:
    a = await automation_service.get_automation(session, automation_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Automation not found")
    if a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your automation")
    execs = await automation_service.get_execution_history(session, automation_id, limit=limit)
    return [schemas.AutomationExecutionRead.model_validate(e) for e in execs]
