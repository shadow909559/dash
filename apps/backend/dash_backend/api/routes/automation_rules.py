"""REST API routes for automation rules management (frontend-facing)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.automation import service as automation_service
from dash_backend.automation.schemas import AutomationCreate, AutomationRead

router = APIRouter(prefix="/automation/rules", tags=["automation"])


class RuleCreate(BaseModel):
    name: str = Field(..., max_length=128)
    trigger: str = Field(..., max_length=32)
    action: str = Field(..., max_length=128)
    enabled: bool = True


class RuleRead(BaseModel):
    id: str
    name: str
    trigger: str
    action: str
    enabled: bool


class RuleToggle(BaseModel):
    enabled: bool


@router.get("", response_model=List[RuleRead])
async def list_rules(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> List[RuleRead]:
    """List all automation rules for the current user."""
    autos = await automation_service.list_automations(session, user.id)
    return [
        RuleRead(
            id=str(a.id),
            name=a.name,
            trigger=a.trigger_type,
            action=a.tool_name,
            enabled=a.enabled,
        )
        for a in autos
    ]


@router.post("", response_model=RuleRead, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: RuleCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RuleRead:
    """Create a new automation rule."""
    auto = await automation_service.create_automation(
        session,
        user.id,
        name=payload.name,
        description=None,
        trigger_type=payload.trigger,
        schedule=None,
        tool_name=payload.action,
        tool_arguments=None,
        enabled=payload.enabled,
    )
    return RuleRead(
        id=str(auto.id),
        name=auto.name,
        trigger=auto.trigger_type,
        action=auto.tool_name,
        enabled=auto.enabled,
    )


@router.patch("/{rule_id}", response_model=RuleRead)
async def toggle_rule(
    rule_id: str,
    payload: RuleToggle,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RuleRead:
    """Toggle an automation rule on/off."""
    rid = uuid.UUID(rule_id) if isinstance(rule_id, str) else rule_id
    a = await automation_service.get_automation(session, rid)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your rule")
    updated = await automation_service.update_automation(session, rid, enabled=payload.enabled)
    return RuleRead(
        id=str(updated.id),
        name=updated.name,
        trigger=updated.trigger_type,
        action=updated.tool_name,
        enabled=updated.enabled,
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an automation rule."""
    rid = uuid.UUID(rule_id) if isinstance(rule_id, str) else rule_id
    a = await automation_service.get_automation(session, rid)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if a.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your rule")
    await automation_service.delete_automation(session, rid)
    return None
