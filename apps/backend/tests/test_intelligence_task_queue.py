"""TaskQueue / scheduler-agent pins (decisions.md #141).

Before #141 the scheduler agent called ``queue.enqueue`` — a method that
did not exist — swallowed the AttributeError and returned a fabricated
``{"scheduled": True, "task_id": "manual"}`` for EVERY action. These tests
pin the real behavior:

- arbitrary schedule payloads (naive/aware/ISO/epoch) normalize to aware UTC
- invalid schedule input fails honestly at the enqueue boundary
- sync handlers execute (they used to die in ``wait_for``) alongside async
- future-scheduled tasks run exactly once, when due
- the shared singletons carry state across event-loop restarts
- the agent's schedule/list/cancel hit the real queue, end to end
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest

from dash_backend.intelligence import task_queue as tq
from dash_backend.intelligence import workflow_engine as we
from dash_backend.agents.ecosystem.scheduler_agent import SchedulerAgent


@pytest.fixture(autouse=True)
def _reset_shared_singletons():
    """Keep module-level singleton state from leaking between tests."""
    saved = (tq._shared_queue, tq._shared_queue_loop,
             we._shared_workflow_engine, we._shared_workflow_engine_loop)
    tq._shared_queue = None
    tq._shared_queue_loop = None
    we._shared_workflow_engine = None
    we._shared_workflow_engine_loop = None
    yield
    tq._shared_queue, tq._shared_queue_loop = saved[0], saved[1]
    we._shared_workflow_engine, we._shared_workflow_engine_loop = saved[2], saved[3]


# ── normalize_to_utc ─────────────────────────────────────────


def test_normalize_matrix_all_forms_same_instant():
    ref_utc = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    ref_local = ref_utc.astimezone()  # same instant, local zone
    epoch = ref_utc.timestamp()

    forms = [
        ref_utc,
        ref_local,                                  # aware, non-UTC zone
        ref_local.replace(tzinfo=None),             # naive -> local wall time
        "2026-09-22T12:00:00Z",
        "2026-09-22T12:00:00+00:00",
        ref_local.isoformat(),                      # ISO with local offset
        epoch,                                      # epoch seconds
        epoch * 1000,                               # epoch milliseconds
        str(int(epoch)),                            # numeric string
    ]
    for value in forms:
        got = tq.normalize_to_utc(value)
        assert got is not None, value
        assert got.tzinfo is not None, value
        assert abs((got - ref_utc).total_seconds()) < 1e-6, value


def test_normalize_none_and_garbage():
    assert tq.normalize_to_utc(None) is None
    assert tq.normalize_to_utc("   ") is None
    with pytest.raises(ValueError):
        tq.normalize_to_utc("not a date")
    with pytest.raises(ValueError):
        tq.normalize_to_utc(object())


async def test_enqueue_invalid_schedule_fails_honestly():
    queue = tq.TaskQueue()
    with pytest.raises(ValueError):
        await queue.enqueue({"name": "x"}, scheduled_at="garbage")
    assert not queue.tasks and not queue.pending_queue


# ── execution semantics ──────────────────────────────────────


async def test_past_due_task_runs_with_sync_handler():
    """Sync handlers used to die in wait_for (TypeError -> retries -> fail)."""
    queue = tq.TaskQueue()
    seen = []
    queue.register_handler("sync.echo", lambda text: seen.append(text) or text)

    await queue.enqueue({"name": "sync.echo", "parameters": {"text": "hi"}},
                        scheduled_at=datetime.now() - timedelta(seconds=1))
    await queue.ensure_started()
    for _ in range(50):
        if seen:
            break
        await asyncio.sleep(0.05)
    await queue.stop()

    assert seen == ["hi"]
    task = queue.list_tasks()[0]
    assert task.status == tq.TaskStatus.COMPLETED
    assert task.result == "hi"


async def test_future_task_runs_once_when_due_not_early():
    queue = tq.TaskQueue()
    seen = []

    await queue.enqueue({"name": "timed",
                         "parameters": {}},
                        scheduled_at=datetime.now(timezone.utc) + timedelta(seconds=0.4),
                        handler=lambda: seen.append(1))
    await queue.ensure_started()
    await asyncio.sleep(0.15)
    assert not seen, "task ran before its schedule time"
    await asyncio.sleep(0.6)
    await queue.stop()

    assert len(seen) == 1
    task = queue.list_tasks()[0]
    assert task.status == tq.TaskStatus.COMPLETED


async def test_handlerless_task_fails_honestly_at_fire_time():
    queue = tq.TaskQueue()
    await queue.enqueue({"name": "nobody_registered_this"},
                        scheduled_at=datetime.now(timezone.utc) + timedelta(seconds=0.2))
    # Disable the default retry policy so the pin fails fast instead of
    # legitimately burning retry_delay * attempt seconds before FAILED.
    queue.list_tasks()[0].max_retries = 0
    await queue.ensure_started()
    for _ in range(50):
        if queue.list_tasks()[0].status in (tq.TaskStatus.FAILED, tq.TaskStatus.COMPLETED):
            break
        await asyncio.sleep(0.05)
    await queue.stop()

    task = queue.list_tasks()[0]
    assert task.status == tq.TaskStatus.FAILED
    assert "No handler found" in task.error


async def test_async_timeout_still_enforced():
    queue = tq.TaskQueue()

    async def slow():
        await asyncio.sleep(5)

    task = tq.Task(name="slow", handler=slow)
    task.timeout = 0.1
    task.max_retries = 0
    with pytest.raises(Exception, match="timed out"):
        await queue.execute_task(task)
    assert task.status == tq.TaskStatus.FAILED


# ── shared singletons / loop rebinding ───────────────────────


async def test_shared_queue_idempotent_and_rebinding():
    q1 = tq.get_shared_task_queue()
    q2 = tq.get_shared_task_queue()
    assert q1 is q2  # same loop -> same instance

    q1.register_handler("carry.me", lambda: None)
    carried = tq.Task(name="carry.me")
    q1.add_task(carried)
    inflight = tq.Task(name="was.running", status=tq.TaskStatus.RUNNING)
    q1.add_task(inflight)

    # Simulate a process restart of the event loop (new thread, new loop).
    result: dict = {}

    def _in_new_loop():
        async def inner():
            fresh = tq.get_shared_task_queue()
            result["queue"] = fresh
            result["handlers"] = dict(fresh.task_handlers)
            result["pending_names"] = sorted(
                fresh.tasks[t].name for t in fresh.pending_queue
            )
            result["inflight_status"] = fresh.tasks[inflight.id].status
        asyncio.run(inner())

    thread = threading.Thread(target=_in_new_loop)
    thread.start()
    thread.join(10)

    fresh = result["queue"]
    assert fresh is not q1, "loop change must rebind the shared queue"
    assert result["handlers"].get("carry.me") is not None
    assert carried.name in result["pending_names"]
    assert result["inflight_status"] == tq.TaskStatus.PENDING


async def test_shared_workflow_engine_carries_workflows():
    engine = we.get_shared_workflow_engine()
    steps = [we.WorkflowStep(type=we.StepType.DELAY, delay=0.01)]
    wf = engine.create_workflow("t", "d", "manual", steps)

    def _in_new_loop():
        async def inner():
            fresh = we.get_shared_workflow_engine()
            assert wf.id in fresh.workflows
        asyncio.run(inner())

    thread = threading.Thread(target=_in_new_loop)
    thread.start()
    thread.join(10)


async def test_workflow_sync_action_handler_executes():
    """Workflow ACTION steps had the same wait_on-sync TypeError bug."""
    engine = we.get_shared_workflow_engine()
    engine.register_action("sync.action", lambda **kw: {"echo": kw})
    steps = [we.WorkflowStep(type=we.StepType.ACTION, action="sync.action",
                             parameters={"x": 1})]
    wf = engine.create_workflow("s", "d", "manual", steps)
    result = await engine.execute_workflow(wf.id)
    assert result == [{"echo": {"x": 1}}]  # list of per-step results
    assert wf.state == we.WorkflowState.COMPLETED


# ── scheduler agent end-to-end ───────────────────────────────


async def test_agent_schedule_list_cancel_end_to_end():
    agent = SchedulerAgent()
    queue = tq.get_shared_task_queue()

    out = await agent.execute({
        "action": "schedule",
        "task": {"name": "agent.pin", "parameters": {}},
        "at": "2026-09-22T12:00:00Z",
        "priority": "HIGH",
    })
    assert out["scheduled"] is True
    task_id = out["task_id"]
    assert task_id != "manual"

    stored = queue.get_task(task_id)
    assert stored is not None
    assert stored.scheduled_at == datetime(2026, 9, 22, 12, 0, 0,
                                           tzinfo=timezone.utc)
    assert stored.priority == tq.TaskPriority.HIGH

    listing = await agent.execute({"action": "list"})
    ids = [item["task_id"] for item in listing["scheduled"]]
    assert task_id in ids

    cancelled = await agent.execute({"action": "cancel", "task_id": task_id})
    assert cancelled["cancelled"] is True
    assert stored.status == tq.TaskStatus.CANCELLED

    miss = await agent.execute({"action": "cancel", "task_id": "nope"})
    assert miss["cancelled"] is False and miss["error"] == "task not found"


async def test_agent_schedule_without_handler_warns():
    agent = SchedulerAgent()
    out = await agent.execute({
        "action": "schedule",
        "task": {"name": "unregistered_handler_name"},
        "at": datetime.now(timezone.utc) + timedelta(hours=1),
    })
    assert out["scheduled"] is True
    assert "warning" in out


async def test_agent_invalid_schedule_raises_not_fabricates():
    """The old code returned fabricated success on ANY error. Never again."""
    agent = SchedulerAgent()
    with pytest.raises(ValueError):
        await agent.execute({
            "action": "schedule",
            "task": {"name": "x"},
            "at": "definitely not a time",
        })


async def test_agent_cancel_requires_task_id():
    agent = SchedulerAgent()
    with pytest.raises(ValueError):
        await agent.execute({"action": "cancel"})


async def test_agent_run_workflow_requires_id():
    agent = SchedulerAgent()
    with pytest.raises(ValueError):
        await agent.execute({"action": "run_workflow"})
