from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.executive import service as exec_service
from dash_backend.executive import schemas
from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.session import get_db_session
from dash_backend.db.models.user import User

router = APIRouter(prefix="/executive", tags=["executive"])

_NOT_FOUND = dict(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
_TASK_NOT_FOUND = dict(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")


async def _owned_goal(goal_id: uuid.UUID, user: User, session: AsyncSession):
    goal = await exec_service.get_goal_for_user(session, user.id, goal_id)
    if goal is None:
        raise HTTPException(**_NOT_FOUND)
    return goal


async def _owned_task(task_id: uuid.UUID, user: User, session: AsyncSession):
    task = await exec_service.get_task_for_user(session, user.id, task_id)
    if task is None:
        raise HTTPException(**_TASK_NOT_FOUND)
    return task


# ---------------------------------------------------------------------------
# Deadline feed (declared before /goals/{goal_id} so "upcoming" is not a uuid)
# ---------------------------------------------------------------------------


@router.get("/goals/upcoming", response_model=schemas.UpcomingResponse)
async def upcoming_deadlines(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.UpcomingResponse:
    items = await exec_service.upcoming_deadlines(session, user.id, days=days)
    return schemas.UpcomingResponse(window_days=days, count=len(items), items=items)


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


@router.post("/goals", response_model=schemas.GoalRead, status_code=status.HTTP_201_CREATED)
async def create_goal(
    payload: schemas.GoalCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.GoalRead:
    goal = await exec_service.create_goal(
        session, user.id, payload.name, payload.description, priority=payload.priority, deadline=payload.deadline
    )
    return schemas.GoalRead.model_validate(goal)


@router.get("/goals", response_model=List[schemas.GoalRead])
async def list_goals(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> List[schemas.GoalRead]:
    goals = await exec_service.list_goals_for_user(session, user.id)
    return [schemas.GoalRead.model_validate(g) for g in goals]


@router.get("/goals/{goal_id}", response_model=schemas.GoalDetail)
async def goal_detail(
    goal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.GoalDetail:
    goal = await _owned_goal(goal_id, user, session)
    progress = await exec_service.goal_progress(session, goal)
    tasks = await exec_service.get_tasks_for_goal(session, goal_id)
    data = schemas.GoalRead.model_validate(goal).model_dump()
    return schemas.GoalDetail(
        **data,
        progress=schemas.GoalProgress(**progress),
        tasks=[schemas.TaskRead.model_validate(t) for t in tasks],
    )


@router.patch("/goals/{goal_id}", response_model=schemas.GoalRead)
async def update_goal(
    goal_id: uuid.UUID,
    payload: schemas.GoalUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.GoalRead:
    goal = await _owned_goal(goal_id, user, session)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    if fields.get("status") not in (None, "pending", "running", "completed", "failed", "cancelled"):
        raise HTTPException(status_code=422, detail=f"Invalid status: {fields['status']}")
    goal = await exec_service.update_goal(session, goal, fields)
    return schemas.GoalRead.model_validate(goal)


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    goal = await _owned_goal(goal_id, user, session)
    await exec_service.delete_goal(session, goal)


@router.post("/goals/{goal_id}/start", response_model=schemas.StartGoalResponse)
async def start_goal(goal_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> schemas.StartGoalResponse:
    goal = await _owned_goal(goal_id, user, session)
    await exec_service.start_goal(session, goal_id)
    return schemas.StartGoalResponse(goal_id=goal_id, started=True, message="Goal started")


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@router.get("/goals/{goal_id}/tasks", response_model=List[schemas.TaskRead])
async def list_tasks(goal_id: uuid.UUID, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)) -> List[schemas.TaskRead]:
    goal = await _owned_goal(goal_id, user, session)
    tasks = await exec_service.get_tasks_for_goal(session, goal.id)
    return [schemas.TaskRead.model_validate(t) for t in tasks]


@router.post("/goals/{goal_id}/tasks", response_model=schemas.TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    goal_id: uuid.UUID,
    payload: schemas.TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.TaskRead:
    goal = await _owned_goal(goal_id, user, session)
    task = await exec_service.create_task(
        session,
        goal,
        payload.name,
        description=payload.description,
        priority=payload.priority,
        deadline=payload.deadline,
        depends_on=[str(d) for d in (payload.depends_on or [])],
    )
    return schemas.TaskRead.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=schemas.TaskRead)
async def update_task(
    task_id: uuid.UUID,
    payload: schemas.TaskUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.TaskRead:
    task = await _owned_task(task_id, user, session)
    fields = {k: v for k, v in payload.model_dump().items() if v is not None}
    task = await exec_service.update_task(session, task, fields)
    return schemas.TaskRead.model_validate(task)


@router.post("/tasks/{task_id}/complete", response_model=schemas.CompleteTaskResponse)
async def complete_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> schemas.CompleteTaskResponse:
    task = await _owned_task(task_id, user, session)
    result = await exec_service.complete_task(session, task)
    return schemas.CompleteTaskResponse(
        completed=result["completed"],
        task_id=task.id,
        goal_completed=result.get("goal_completed", False),
        blocked_by=result.get("blocked_by"),
    )


# ---------------------------------------------------------------------------
# Operational admin endpoints (single-user system; still requires authentication)
# ---------------------------------------------------------------------------


@router.get("/admin/claimed-tasks")
async def list_claimed_tasks(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """List tasks currently claimed by workers (for operational visibility)."""
    from sqlalchemy import text

    stmt = await session.execute(text("SELECT id, goal_id, claimed_by, claimed_at, last_heartbeat, metadata FROM executive_tasks WHERE claimed_by IS NOT NULL ORDER BY last_heartbeat DESC"))
    rows = stmt.fetchall()
    items = []
    for r in rows:
        items.append(
            {
                "task_id": str(r[0]),
                "goal_id": str(r[1]) if r[1] else None,
                "claimed_by": str(r[2]) if r[2] else None,
                "claimed_at": r[3].isoformat() if r[3] else None,
                "last_heartbeat": r[4].isoformat() if r[4] else None,
                "metadata": r[5],
            }
        )
    return {"claimed_tasks": items}


@router.post("/admin/reset-stuck")
async def reset_stuck(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db_session)):
    """Manually trigger stuck-task reset (resets tasks with stale heartbeats)."""
    count = await exec_service.reset_stuck_tasks(session, stuck_seconds=60.0)
    return {"reset_count": count}
