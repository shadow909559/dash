"""Agent service: CRUD and registry helpers."""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.agents import models
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


async def create_agent(session: AsyncSession, name: str, description: str | None, system_prompt: str | None, allowed_tools: list[str] | None) -> models.Agent:
    agent = models.Agent(name=name, description=description, system_prompt=system_prompt, allowed_tools=allowed_tools)
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    logger.info("Created agent %s", agent.id)
    return agent


async def list_agents(session: AsyncSession) -> List[models.Agent]:
    stmt = select(models.Agent).order_by(models.Agent.created_at.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_agent(session: AsyncSession, agent_id: str | uuid.UUID) -> models.Agent | None:
    aid = uuid.UUID(agent_id) if isinstance(agent_id, str) else agent_id
    return await session.get(models.Agent, aid)


async def update_agent(session: AsyncSession, agent_id: str | uuid.UUID, **kwargs) -> models.Agent | None:
    aid = uuid.UUID(agent_id) if isinstance(agent_id, str) else agent_id
    allowed = {"name", "description", "system_prompt", "allowed_tools"}
    update_data = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not update_data:
        return await get_agent(session, aid)
    stmt = update(models.Agent).where(models.Agent.id == aid).values(**update_data)
    await session.execute(stmt)
    await session.commit()
    return await get_agent(session, aid)
