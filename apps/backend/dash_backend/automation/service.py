"""Automation service: CRUD and execution helpers."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.automation import models
from dash_backend.logging_config import get_logger
from dash_backend.tools.tool_manager import get_tool_manager, ToolCallRequest
from dash_backend.tools.base_tool import ToolContext

logger = get_logger(__name__)


async def create_automation(
    session: AsyncSession,
    user_id: str | uuid.UUID,
    name: str,
    description: str | None,
    trigger_type: str,
    schedule: str,
    tool_name: str,
    tool_arguments: dict[str, Any] | None = None,
    enabled: bool = True,
) -> models.Automation:
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    auto = models.Automation(
        user_id=uid,
        name=name,
        description=description,
        trigger_type=trigger_type,
        schedule=schedule,
        tool_name=tool_name,
        tool_arguments=tool_arguments,
        enabled=enabled,
    )
    session.add(auto)
    await session.commit()
    await session.refresh(auto)
    logger.info("Created automation %s for user %s", auto.id, uid)
    return auto


async def list_automations(session: AsyncSession, user_id: str | uuid.UUID) -> List[models.Automation]:
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    stmt = select(models.Automation).where(models.Automation.user_id == uid).order_by(models.Automation.created_at.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_automation(session: AsyncSession, automation_id: str | uuid.UUID) -> models.Automation | None:
    aid = uuid.UUID(automation_id) if isinstance(automation_id, str) else automation_id
    return await session.get(models.Automation, aid)


async def update_automation(session: AsyncSession, automation_id: str | uuid.UUID, **kwargs: Any) -> models.Automation | None:
    aid = uuid.UUID(automation_id) if isinstance(automation_id, str) else automation_id
    allowed = {"name", "description", "trigger_type", "schedule", "tool_name", "tool_arguments", "enabled"}
    update_data = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not update_data:
        return await get_automation(session, aid)
    stmt = update(models.Automation).where(models.Automation.id == aid).values(**update_data)
    await session.execute(stmt)
    await session.commit()
    return await get_automation(session, aid)


async def delete_automation(session: AsyncSession, automation_id: str | uuid.UUID) -> bool:
    aid = uuid.UUID(automation_id) if isinstance(automation_id, str) else automation_id
    a = await session.get(models.Automation, aid)
    if a is None:
        return False
    await session.delete(a)
    await session.commit()
    return True


async def execute_automation(session: AsyncSession, automation: models.Automation) -> dict[str, Any]:
    """Execute a configured automation by invoking the configured tool through ToolManager.

    Persist an AutomationExecution record for every run.
    """
    manager = get_tool_manager()
    # Build tool call request
    call = ToolCallRequest(tool_name=automation.tool_name, arguments=automation.tool_arguments or {})

    # Build a minimal tool context (no conversation/request id in automated runs)
    ctx = ToolContext(user_id=str(automation.user_id), working_directory=".")

    try:
        result = await manager.execute_tool(call, ctx)

        # Persist execution record
        try:
            exec_record = models.AutomationExecution(
                automation_id=automation.id,
                status=result.status.name,
                summary=result.summary,
                output=result.output,
                error=result.error_message or None,
            )
            session.add(exec_record)
        except Exception:
            logger.exception("Failed to create AutomationExecution record")

        # record execution by touching updated_at on automation
        automation.updated_at = datetime.utcnow()
        session.add(automation)
        await session.commit()

        logger.info("Executed automation %s -> tool=%s status=%s", automation.id, automation.tool_name, result.status)
        return {
            "status": result.status.name,
            "summary": result.summary,
            "output": result.output,
            "error": result.error_message,
        }
    except Exception as exc:
        logger.exception("Automation %s execution failed: %s", automation.id, exc)
        # Try to persist failure
        try:
            fail_record = models.AutomationExecution(
                automation_id=automation.id,
                status="ERROR",
                summary="",
                output=None,
                error=str(exc),
            )
            session.add(fail_record)
            await session.commit()
        except Exception:
            logger.exception("Failed to persist failed AutomationExecution")
        return {"status": "error", "error": str(exc)}


# Lightweight helper used by scheduler to fetch due automations (interval/cron)
async def fetch_enabled_automations(session: AsyncSession) -> List[models.Automation]:
    stmt = select(models.Automation).where(models.Automation.enabled == True)
    res = await session.execute(stmt)
    return list(res.scalars().all())
