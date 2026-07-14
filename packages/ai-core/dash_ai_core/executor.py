"""Executor.

Executes a planned set of steps by invoking agents and optionally tools.

No LLM API calls are made.
"""

from __future__ import annotations

from typing import Any, Mapping

from .agent_registry import AgentRegistry
from .models import AgentResult, OrchestrationResult, Plan, Task
from .task_queue import TaskQueue
from .tool_registry import ToolRegistry


class Executor:
    def __init__(
        self,
        *,
        agent_registry: AgentRegistry,
        task_queue: TaskQueue,
        tool_registry: ToolRegistry,
    ) -> None:
        self._agent_registry = agent_registry
        self._task_queue = task_queue
        self._tool_registry = tool_registry

    def execute(self, user_request: str, plan: Plan) -> OrchestrationResult:
        executed_agent_ids: list[str] = []
        last_output: dict[str, Any] = {}

        for i, step in enumerate(plan.steps):
            task = Task(
                id=f"task_{i}",
                user_request=user_request,
                input=dict(step.input),
            )
            self._task_queue.enqueue(task)

            dequeued = self._task_queue.dequeue(timeout_s=0)
            # For this in-process executor, dequeue must succeed.
            if dequeued is None:
                raise RuntimeError("Task queue did not yield task")

            agent = self._agent_registry.get(step.agent_id)
            agent_result: AgentResult = agent.execute(
                dequeued,
                tool_context={
                    "tool_registry": self._tool_registry,
                },
            )

            executed_agent_ids.append(agent.id)
            last_output = dict(agent_result.output)

        return OrchestrationResult(output=last_output, executed_agent_ids=executed_agent_ids)

