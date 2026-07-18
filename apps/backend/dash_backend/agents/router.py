"""FastAPI router for agent management."""

from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.agents import schemas
from dash_backend.agents import service as agent_service
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.session import get_db_session
from dash_backend.db.models.user import User

router = APIRouter(prefix="", tags=["agents"])


@router.get("/agents", response_model=List[schemas.AgentRead])
async def list_agents(session: AsyncSession = Depends(get_db_session)) -> List[schemas.AgentRead]:
    agents = await agent_service.list_agents(session)
    return [schemas.AgentRead.model_validate(a) for a in agents]


@router.post("/agents", response_model=schemas.AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(payload: schemas.AgentCreate, session: AsyncSession = Depends(get_db_session)) -> schemas.AgentRead:
    agent = await agent_service.create_agent(session, payload.name, payload.description, payload.system_prompt, payload.allowed_tools)
    return schemas.AgentRead.model_validate(agent)


@router.patch("/agents/{agent_id}", response_model=schemas.AgentRead)
async def patch_agent(agent_id: uuid.UUID, payload: schemas.AgentUpdate, session: AsyncSession = Depends(get_db_session)) -> schemas.AgentRead:
    a = await agent_service.get_agent(session, agent_id)
    if a is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    updated = await agent_service.update_agent(session, agent_id, **payload.model_dump(exclude_none=True))
    return schemas.AgentRead.model_validate(updated)
