"""REST endpoints for the persistent task orchestrator (decisions.md #90).

Mounted under the existing ``/agent`` prefix (same router group as the
goal API, paths do not collide):

    POST /api/v1/agent/task            — create + plan + run a complex goal
    GET  /api/v1/agent/tasks           — list all tasks (current snapshots)
    GET  /api/v1/agent/task/{task_id}  — one task snapshot (steps, report)
    POST /api/v1/agent/task/{task_id}/approve?approved=true|false
    POST /api/v1/agent/task/{task_id}/pause
    POST /api/v1/agent/task/{task_id}/resume
    POST /api/v1/agent/task/{task_id}/cancel
    POST /api/v1/agent/task/{task_id}/replan  { "instruction": "..." }
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent-tasks"])


class TaskCreateRequest(BaseModel):
    goal: str
    context: dict = {}


class ReplanRequest(BaseModel):
    instruction: str


class ApproveRequest(BaseModel):
    approved: bool = True
    step_id: str | None = None  # explicit gate target (multi-gate tasks)


@router.post("/task")
async def create_task(req: TaskCreateRequest, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    if not req.goal.strip():
        raise HTTPException(status_code=422, detail="goal must not be empty")
    try:
        task = await get_task_orchestrator().create_task(
            req.goal.strip(), user_id=user_id, context=req.context or None,
        )
    except ValueError as exc:
        # Candor refusal or concurrency limit — a named client error
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return task.to_dict()


@router.get("/tasks")
async def list_tasks(user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    return {"tasks": get_task_orchestrator().list_tasks()}


@router.get("/task/{task_id}")
async def get_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    task = get_task_orchestrator().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task.to_dict(include_events=True)


@router.post("/task/{task_id}/approve")
async def approve_task(task_id: str, req: ApproveRequest, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    ok = await get_task_orchestrator().approve_step(
        task_id, req.approved, step_id=req.step_id or None,
    )
    if not ok:
        raise HTTPException(status_code=409, detail="Task is not waiting for confirmation")
    return {"success": True, "approved": req.approved}


@router.post("/task/{task_id}/pause")
async def pause_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    ok = await get_task_orchestrator().pause_task(task_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Task is not pausable in its current state")
    return {"success": True}


@router.post("/task/{task_id}/resume")
async def resume_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    ok = await get_task_orchestrator().resume_task(task_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Task is not paused")
    return {"success": True}


@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    ok = await get_task_orchestrator().cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=409, detail="Task is already terminal")
    return {"success": True}


@router.post("/task/{task_id}/replan")
async def replan_task(task_id: str, req: ReplanRequest, user_id: str = Depends(get_current_user_id)):
    from dash_backend.autonomous.task_orchestrator import get_task_orchestrator

    ok = await get_task_orchestrator().replan_task(task_id, req.instruction.strip())
    if not ok:
        raise HTTPException(status_code=409, detail="Task cannot be replanned in its current state")
    return {"success": True}
