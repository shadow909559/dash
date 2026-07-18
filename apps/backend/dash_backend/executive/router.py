from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.executive import service as exec_service
from dash_backend.executive import schemas
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.session import get_db_session
from dash_backend.db.models.user import User

router = APIRouter(prefix="/api/v1/executive", tags=["executive"])


@router.post("/goals", response_model=schemas.GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: schemas.GoalCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.GoalRead:
    goal = await exec_service.create_goal(session, user.id, payload.name, payload.description)
    return schemas.GoalRead.model_validate(goal)


@router.get("/goals", response_model=List[schemas.GoalRead])
async def list_goals(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> List[schemas.GoalRead]:
    goals = await exec_service.list_goals_for_user(session, user.id)
    return [schemas.GoalRead.model_validate(g) for g in goals]


@router.get("/goals/{goal_id}/tasks", response_model=List[schemas.TaskRead])
async def list_tasks(goal_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> List[schemas.TaskRead]:
    goal = await session.get(exec_service.executive_models.Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    if goal.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your goal")
    tasks = await exec_service.get_tasks_for_goal(session, goal_id)
    return [schemas.TaskRead.model_validate(t) for t in tasks]


@router.post("/goals/{goal_id}/start", response_model=schemas.StartGoalResponse)
async def start_goal(goal_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> schemas.StartGoalResponse:
    goal = await session.get(exec_service.executive_models.Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    if goal.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your goal")
    await exec_service.start_goal(session, goal_id)
    return schemas.StartGoalResponse(goal_id=goal_id, started=True, message="Goal started")


# Operational admin endpoints (single-user system; still requires authentication)
@router.get("/admin/claimed-tasks")
async def list_claimed_tasks(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """List tasks currently claimed by workers (for operational visibility)."""
    from sqlalchemy import text
    stmt = await session.execute(text("SELECT id, goal_id, claimed_by, claimed_at, last_heartbeat, metadata FROM executive_tasks WHERE claimed_by IS NOT NULL ORDER BY last_heartbeat DESC"))
    rows = stmt.fetchall()
    items = []
    for r in rows:
        items.append({
            "task_id": str(r[0]),
            "goal_id": str(r[1]) if r[1] else None,
            "claimed_by": str(r[2]) if r[2] else None,
            "claimed_at": r[3].isoformat() if r[3] else None,
            "last_heartbeat": r[4].isoformat() if r[4] else None,
            "metadata": r[5],
        })
    return {"claimed_tasks": items}


@router.post("/admin/reset-stuck")
async def reset_stuck(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """Manually trigger stuck-task reset (resets tasks with stale heartbeats)."""
    count = await exec_service.reset_stuck_tasks(session, stuck_seconds=60.0)
    return {"reset_count": count}
