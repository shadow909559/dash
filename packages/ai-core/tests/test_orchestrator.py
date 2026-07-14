"""Unit tests for DASH AI core orchestration."""

from __future__ import annotations

from typing import Mapping

import pytest

from dash_ai_core.agent_interface import Agent
from dash_ai_core.agent_registry import AgentRegistry
from dash_ai_core.executor import Executor
from dash_ai_core.models import AgentResult, Task
from dash_ai_core.orchestrator import Orchestrator
from dash_ai_core.planner import Planner
from dash_ai_core.task_queue import TaskQueue
from dash_ai_core.tool_registry import ToolRegistry


class EchoAgent:
    def __init__(self, agent_id: str) -> None:
        self._id = agent_id

    @property
    def id(self) -> str:
        return self._id

    @property
    def capabilities(self) -> list[str]:
        return ["echo"]

    def can_handle(self, user_request: str) -> bool:
        return "echo" in user_request

    def execute(self, task: Task, *, tool_context: Mapping[str, object]) -> AgentResult:
        # No tool execution; return deterministic output.
        return AgentResult(output={"agent_id": self._id, "input": dict(task.input)})


def test_orchestrator_empty_plan() -> None:
    registry = AgentRegistry()
    planner = Planner(agent_registry=registry)
    executor = Executor(agent_registry=registry, task_queue=TaskQueue(), tool_registry=ToolRegistry())
    orchestrator = Orchestrator(planner=planner, executor=executor)

    result = orchestrator.handle("nothing to do")
    assert result.output == {}
    assert result.executed_agent_ids == []


def test_orchestrator_executes_agent_steps() -> None:
    registry = AgentRegistry()
    registry.register(EchoAgent("echo_1"))
    registry.register(EchoAgent("echo_2"))

    planner = Planner(agent_registry=registry)
    executor = Executor(agent_registry=registry, task_queue=TaskQueue(), tool_registry=ToolRegistry())
    orchestrator = Orchestrator(planner=planner, executor=executor)

    result = orchestrator.handle("please echo", context={"x": 1})

    # Both agents can handle: planner creates two steps; executor keeps last output.
    assert result.executed_agent_ids == ["echo_1", "echo_2"]
    assert result.output["agent_id"] == "echo_2"
    assert result.output["input"] == {"x": 1}

