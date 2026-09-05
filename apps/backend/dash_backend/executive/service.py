from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.session import get_db_session, AsyncSessionLocal
from dash_backend.executive import models as executive_models
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _to_uuid(val: Any) -> Optional[uuid.UUID]:
    """Convert a value to uuid.UUID, returning None if not possible."""
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return None


async def _queue_goal_sync(session: AsyncSession, goal: executive_models.Goal, operation: str = "upsert") -> None:
    """Best-effort outbox write after a durable local project change."""
    from dash_backend.sync.outbox import enqueue_event

    await enqueue_event(
        session,
        record_type="project",
        record_id=goal.id,
        owner_id=goal.user_id,
        operation=operation,
        payload={
            "name": goal.name,
            "description": goal.description,
            "status": goal.status,
            "created_at": goal.created_at.isoformat(),
            "updated_at": goal.updated_at.isoformat(),
            "deleted_at": None,
        },
    )


async def create_goal(session: AsyncSession, user_id: uuid.UUID, name: str, description: Optional[str] = None) -> executive_models.Goal:
    goal = executive_models.Goal(user_id=user_id, name=name, description=description)
    session.add(goal)
    await session.commit()
    await session.refresh(goal)
    await _queue_goal_sync(session, goal)
    logger.info("Created goal %s for user %s", goal.id, user_id)
    return goal


async def list_goals_for_user(session: AsyncSession, user_id: uuid.UUID) -> List[executive_models.Goal]:
    stmt = select(executive_models.Goal).where(executive_models.Goal.user_id == user_id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def get_tasks_for_goal(session: AsyncSession, goal_id: uuid.UUID) -> List[executive_models.ExecutiveTask]:
    stmt = select(executive_models.ExecutiveTask).where(executive_models.ExecutiveTask.goal_id == goal_id)
    res = await session.execute(stmt)
    return list(res.scalars().all())


async def start_goal(session: AsyncSession, goal_id: uuid.UUID) -> bool:
    stmt = (
        update(executive_models.ExecutiveTask)
        .where(
            executive_models.ExecutiveTask.goal_id == goal_id,
            executive_models.ExecutiveTask.status == "pending",
        )
        .values(status="queued")
    )
    res = await session.execute(stmt)
    await session.commit()
    return res.rowcount > 0


async def decompose_goal_into_tasks(session: AsyncSession, goal: executive_models.Goal) -> List[executive_models.ExecutiveTask]:
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
            candidates.extend([s.strip() for s in part.split(".") if s.strip()])
        if not candidates:
            candidates = [goal.name]
        plan_items = [{"name": c[:255], "description": c, "est_minutes": None, "tools": []} for c in candidates]

    tasks: List[executive_models.ExecutiveTask] = []
    for idx, item in enumerate(plan_items):
        name = item.get("name") or f"task-{idx}"
        desc = item.get("description") or ""
        task = executive_models.ExecutiveTask(goal_id=goal.id, name=name[:255], description=desc[:1000], meta_data={"index": idx, "est_minutes": item.get("est_minutes"), "tools": item.get("tools", [])})
        session.add(task)
        tasks.append(task)

    await session.commit()
    for task in tasks:
        await session.refresh(task)
        await _queue_task_sync(session, task, goal.user_id)
    logger.info("Decomposed goal %s into %d tasks", goal.id, len(tasks))
    return tasks


async def _queue_task_sync(
    session: AsyncSession, task: executive_models.ExecutiveTask, owner_id: uuid.UUID, operation: str = "upsert"
) -> None:
    from dash_backend.sync.outbox import enqueue_event

    await enqueue_event(
        session,
        record_type="task",
        record_id=task.id,
        owner_id=owner_id,
        operation=operation,
        payload={
            "project_id": str(task.goal_id),
            "title": task.name,
            "description": task.description,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "deleted_at": None,
        },
    )


async def worker_loop(poll_interval: float = 2.0, stuck_seconds: float = 60.0):
    """Background worker loop that picks pending tasks and runs them safely
    across multiple worker processes. Stuck tasks (no heartbeat within `stuck_seconds`)
    are reset to pending so another worker can pick them up."""
    logger.info("Starting executive worker loop")

    while True:
        try:
            async with AsyncSessionLocal() as session:
                try:
                    # First, reset stuck tasks
                    await reset_stuck_tasks(session, stuck_seconds)

                    # Check if SQLite (no FOR UPDATE SKIP LOCKED support)
                    bind = session.get_bind()
                    is_sqlite = bind.url.get_backend_name() == "sqlite"

                    # Pick one pending task
                    stmt = (
                        select(executive_models.ExecutiveTask)
                        .where(executive_models.ExecutiveTask.status == "pending")
                        .order_by(executive_models.ExecutiveTask.created_at.asc())
                    )
                    if not is_sqlite:
                        stmt = stmt.with_for_update(skip_locked=True)
                    stmt = stmt.limit(1)

                    res = await session.execute(stmt)
                    task_obj = res.scalar_one_or_none()
                    if task_obj:
                        worker_id = uuid.uuid4()
                        now_dt = datetime.now(timezone.utc)
                        task_obj.status = "running"
                        task_obj.claimed_by = worker_id
                        task_obj.claimed_at = now_dt
                        task_obj.last_heartbeat = now_dt
                        task_obj.meta_data = dict(task_obj.meta_data or {})
                        task_obj.meta_data["_claimed_by_worker"] = str(worker_id)
                        session.add(task_obj)

                    if not task_obj:
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
        except Exception:
            logger.exception("Worker session error")
            await asyncio.sleep(poll_interval)


async def reset_stuck_tasks(session: AsyncSession, stuck_seconds: float = 60.0) -> int:
    """Reset tasks that were claimed but have not heartbeat within stuck_seconds."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stuck_seconds)
    stmt = (
        update(executive_models.ExecutiveTask)
        .where(
            executive_models.ExecutiveTask.status == "running",
            (executive_models.ExecutiveTask.last_heartbeat < cutoff) | (executive_models.ExecutiveTask.last_heartbeat.is_(None)),
        )
        .values(status="pending", claimed_by=None, claimed_at=None, last_heartbeat=None)
    )
    res = await session.execute(stmt)
    await session.commit()
    rowcount = res.rowcount if hasattr(res, "rowcount") else 0
    if rowcount:
        logger.info("Reset %d stuck tasks", rowcount)
    return rowcount


async def run_task_with_heartbeat(session: AsyncSession, task: executive_models.ExecutiveTask, heartbeat_interval: float = 5.0) -> dict:
    """Run a task while periodically issuing heartbeats to update last_heartbeat.

    The heartbeat is updated in the DB so other workers can detect a live worker.
    The actual task execution is delegated to run_pending_task.
    """
    worker_meta = task.meta_data or {}
    worker_id_str = worker_meta.get("_claimed_by_worker")
    worker_uuid = _to_uuid(worker_id_str)
    task_uuid = _to_uuid(task.id)

    # helper to update heartbeat
    async def heartbeat_loop(stop_event: asyncio.Event):
        while not stop_event.is_set():
            try:
                async with AsyncSessionLocal() as hb_sess:
                    from sqlalchemy import text

                    hb_q = text(
                        "UPDATE executive_tasks SET last_heartbeat = :hb WHERE id = :tid AND claimed_by = :worker"
                    )
                    await hb_sess.execute(hb_q, {
                        "hb": datetime.now(timezone.utc),
                        "tid": str(task_uuid),
                        "worker": str(worker_uuid),
                    })
                    await hb_sess.commit()
            except Exception:
                logger.exception("Heartbeat update failed for task %s", task.id)
            await asyncio.sleep(heartbeat_interval)

    stop_evt = asyncio.Event()
    hb_task = asyncio.create_task(heartbeat_loop(stop_evt))
    try:
        result = await run_pending_task(session, task)
        return result
    finally:
        stop_evt.set()
        try:
            await hb_task
        except asyncio.CancelledError:
            pass


async def run_pending_task(session: AsyncSession, task: executive_models.ExecutiveTask) -> dict:
    """Execute the actual pending task logic. Override this with real task execution."""
    logger.info("Running task %s", task.id)
    # Mark task as completed
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "completed", "task_id": str(task.id)}
