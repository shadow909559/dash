from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import List, Optional, Any, Dict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.executive import models as executive_models
from dash_backend.logging_config import get_logger
from dash_backend.skills.skill_router import SkillRouter, SkillContext
from dash_backend.db.session import AsyncSessionLocal
from dash_backend.tools.tool_manager import get_tool_manager

logger = get_logger(__name__)


async def create_goal(session: AsyncSession, user_id: uuid.UUID, name: str, description: Optional[str] = None) -> executive_models.Goal:
    goal = executive_models.Goal(user_id=user_id, name=name, description=description)
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    logger.info("Created goal %s for user %s", goal.id, user_id)
    return goal


async def decompose_goal_into_tasks(session: AsyncSession, goal: executive_models.Goal) -> List[executive_models.Task]:
    """Decompose a goal into structured tasks using the Planner. Falls back to
    a simple heuristic if the Planner/LLM fails or is not configured.
    """
    from dash_backend.executive.planner import Planner

    plan_items = []
    try:
        plan_items = await Planner.decompose(goal.name, goal.description)
    except Exception:
        logger.exception("Planner decomposition failed, falling back to heuristic")

    if not plan_items:
        text = goal.description or goal.name
        candidates: List[str] = []
        for part in (p.strip() for p in text.splitlines() if p.strip()):
            candidates.extend([s.strip() for s in part.split('.') if s.strip()])
        if not candidates:
            candidates = [goal.name]
        plan_items = [{"name": c[:255], "description": c, "est_minutes": None, "tools": []} for c in candidates]

    tasks: List[executive_models.Task] = []
    for idx, item in enumerate(plan_items):
        name = item.get("name") or f"task-{idx}"
        desc = item.get("description") or ""
        task = executive_models.Task(goal_id=goal.id, name=name[:255], description=desc[:1000], meta_data={"index": idx, "est_minutes": item.get("est_minutes"), "tools": item.get("tools", [])})
        session.add(task)
        tasks.append(task)

    await session.commit()
    for task in tasks:
        await session.refresh(task)
    logger.info("Decomposed goal %s into %d tasks", goal.id, len(tasks))
    return tasks


async def list_goals_for_user(session: AsyncSession, user_id: uuid.UUID) -> List[executive_models.Goal]:
    stmt = select(executive_models.Goal).where(executive_models.Goal.user_id == user_id).order_by(executive_models.Goal.created_at.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_tasks_for_goal(session: AsyncSession, goal_id: uuid.UUID) -> List[executive_models.Task]:
    stmt = select(executive_models.Task).where(executive_models.Task.goal_id == goal_id).order_by(executive_models.Task.created_at.asc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def start_goal(session: AsyncSession, goal_id: uuid.UUID) -> bool:
    goal = await session.get(executive_models.Goal, goal_id)
    if goal is None:
        raise ValueError("Goal not found")
    # If no tasks exist, decompose
    stmt = select(executive_models.Task).where(executive_models.Task.goal_id == goal.id)
    res = await session.execute(stmt)
    tasks = list(res.scalars().all())
    if not tasks:
        await decompose_goal_into_tasks(session, goal)
    # mark goal running
    goal.status = "running"
    session.add(goal)
    await session.commit()
    return True


async def run_pending_task(session: AsyncSession, task: executive_models.Task) -> Dict[str, Any]:
    """Execute a single task by routing to a matching skill.

    Returns an execution result dict and writes ExecutionHistory.
    """
    start = datetime.utcnow()
    task.status = "running"
    session.add(task)
    await session.commit()
    await session.refresh(task)

    # Prepare skill router
    tool_manager = get_tool_manager()
    router = SkillRouter(tool_manager)
    context = SkillContext(user_id=str(task.goal_id), session_id=None, extra={"task_id": str(task.id)})
    intent = task.name or (task.description or "run task")

    try:
        result = await router.route(intent=intent, args={}, context=context)
        success = result.get("status") == "ok"
        output = result.get("result")
    except Exception as exc:
        logger.exception("Task execution failed for %s", task.id)
        success = False
        output = {"error": str(exc)}

    duration = (datetime.utcnow() - start).total_seconds() * 1000.0

    # Write execution history
    history = executive_models.ExecutionHistory(task_id=task.id, result=output if isinstance(output, dict) else {"result": output}, duration_ms=duration, success=success)
    session.add(history)

    # Update task status
    task.status = "completed" if success else "failed"
    task.attempt = (task.attempt or 0) + 1
    session.add(task)

    # If all tasks completed, mark goal completed
    await session.commit()
    await session.refresh(task)
    await session.refresh(history)

    # Check goal completeness
    stmt = select(executive_models.Task).where(executive_models.Task.goal_id == task.goal_id)
    res = await session.execute(stmt)
    all_tasks = list(res.scalars().all())
    if all_tasks and all(t.status == "completed" for t in all_tasks):
        goal = await session.get(executive_models.Goal, task.goal_id)
        if goal:
            goal.status = "completed"
            session.add(goal)
            await session.commit()

    return {"task_id": str(task.id), "success": success, "duration_ms": duration, "output": output}


async def worker_loop(poll_interval: float = 2.0, stuck_seconds: float = 60.0):
    """Background worker loop that picks pending tasks and runs them using
    row-level locking (FOR UPDATE SKIP LOCKED) to safely coordinate multiple
    worker processes.

    This implementation opens a transaction, selects one pending task with
    FOR UPDATE SKIP LOCKED, claims it, and then executes the task outside the
    claim transaction. Stuck tasks (no heartbeat within `stuck_seconds`) are
    reset to pending.
    """
    logger.info("Starting executive worker loop")
    try:
        while True:
            async with AsyncSessionLocal() as session:
                try:
                    # Reset stuck tasks
                    try:
                        await reset_stuck_tasks(session, stuck_seconds)
                    except Exception:
                        logger.exception("Failed to reset stuck tasks")

                    # Acquire a pending task using SELECT ... FOR UPDATE SKIP LOCKED
                    async with session.begin():
                        # Use text query to leverage SKIP LOCKED in a portable way
                        from sqlalchemy import text

                        query = text(
                            "SELECT id FROM executive_tasks WHERE status = :pending ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1"
                        )
                        res = await session.execute(query, {"pending": "pending"})
                        row = res.first()
                        if not row:
                            # No pending tasks found in DB transaction
                            pass
                        else:
                            task_id = row[0]
                            # Claim the task by updating its status and claimed_by/claimed_at
                            claim_q = text(
                                "UPDATE executive_tasks SET status = :running, claimed_by = :worker, claimed_at = now(), last_heartbeat = now() WHERE id = :tid RETURNING id"
                            )
                            worker_id = str(uuid.uuid4())
                            claim_res = await session.execute(claim_q, {"running": "running", "worker": worker_id, "tid": str(task_id)})
                            claimed = claim_res.first()
                            if claimed:
                                # refresh to load the task object outside the transaction
                                task_obj = await session.get(executive_models.Task, task_id)
                                # attach worker id to task metadata for heartbeat updates
                                task_obj.meta_data = (task_obj.meta_data or {})
                                task_obj.meta_data["_claimed_by_worker"] = worker_id
                            else:
                                task_obj = None

                    # End transaction scope here
                    if not row or task_obj is None:
                        await asyncio.sleep(poll_interval)
                        continue

                    logger.info("Picked pending task %s claimed_by=%s", task_obj.id, task_obj.meta_data.get("_claimed_by_worker"))
                    try:
                        # Run task and periodically heartbeat
                        await run_task_with_heartbeat(session, task_obj, heartbeat_interval=5.0)
                    except Exception:
                        logger.exception("Failed to execute pending task %s", task_obj.id)
                except Exception:
                    logger.exception("Worker loop error")
            await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.info("Worker loop cancelled, shutting down gracefully")
    except Exception:
        logger.exception("Worker loop terminated due to unexpected error")


async def reset_stuck_tasks(session: AsyncSession, stuck_seconds: float = 60.0) -> int:
    """Reset tasks that were claimed but have not heartbeat within stuck_seconds.

    Returns the number of tasks reset.
    """
    from sqlalchemy import text

    reset_q = text(
        "UPDATE executive_tasks SET status = 'pending', claimed_by = NULL, claimed_at = NULL, last_heartbeat = NULL WHERE status = 'running' AND COALESCE(EXTRACT(EPOCH FROM now() - last_heartbeat), 0) > :stuck"
    )
    res = await session.execute(reset_q, {"stuck": float(stuck_seconds)})
    await session.commit()
    rowcount = res.rowcount if hasattr(res, "rowcount") else 0
    if rowcount:
        logger.info("Reset %d stuck tasks", rowcount)
    return rowcount


async def run_task_with_heartbeat(session: AsyncSession, task: executive_models.Task, heartbeat_interval: float = 5.0) -> dict:
    """Run a task while periodically issuing heartbeats to update last_heartbeat.

    The heartbeat is updated in the DB so other workers can detect a live worker.
    The actual task execution is delegated to run_pending_task.
    """
    worker_meta = task.meta_data or {}
    worker_id = worker_meta.get("_claimed_by_worker")

    # helper to update heartbeat
    async def heartbeat_loop(stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                async with AsyncSessionLocal() as hb_sess:
                    from sqlalchemy import text

                    hb_q = text(
                        "UPDATE executive_tasks SET last_heartbeat = now() WHERE id = :tid AND claimed_by = :worker"
                    )
                    await hb_sess.execute(hb_q, {"tid": str(task.id), "worker": worker_id})
                    await hb_sess.commit()
            except Exception:
                logger.exception("Heartbeat update failed for task %s", task.id)
            await asyncio.sleep(heartbeat_interval)

    stop_evt = asyncio.Event()
    hb_task = asyncio.create_task(heartbeat_loop(stop_evt))
    try:
        result = await run_pending_task(session, task)
    finally:
        stop_evt.set()
        await hb_task
    return result


if __name__ == "__main__":
    try:
        asyncio.run(worker_loop())
    except KeyboardInterrupt:
        logger.info("Worker loop terminated by KeyboardInterrupt")
