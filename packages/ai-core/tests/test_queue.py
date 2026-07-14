"""Unit tests for TaskQueue."""

from __future__ import annotations

from dash_ai_core.models import Task
from dash_ai_core.task_queue import TaskQueue


def test_task_queue_enqueue_dequeue() -> None:
    q = TaskQueue()
    task = Task(id="t1", user_request="req", input={"k": "v"})

    assert q.size() == 0
    q.enqueue(task)
    assert q.size() == 1

    out = q.dequeue(timeout_s=0.1)
    assert out is not None
    assert out.id == "t1"
    assert q.size() == 0

    out2 = q.dequeue(timeout_s=0)
    assert out2 is None

