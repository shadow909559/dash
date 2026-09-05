"""Agent Orchestrator — chains agents for complex tasks using cloud AI.

Simplified version: all LLM calls go through cloud (Groq) for speed.
Each step is typed (plan/code/research/execute/verify) and gets a focused prompt.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class StepType(str, Enum):
    PLAN = "plan"
    CODE = "code"
    RESEARCH = "research"
    EXECUTE = "execute"
    VERIFY = "verify"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrchestratorStep:
    id: str
    index: int
    description: str
    step_type: StepType
    status: StepStatus = StepStatus.PENDING
    result: str = ""
    error: str = ""
    agent: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id, "index": self.index,
            "description": self.description,
            "type": self.step_type.value,
            "status": self.status.value,
            "result": self.result[:500] if self.result else "",
            "error": self.error, "agent": self.agent,
            "duration_ms": int((self.completed_at - self.started_at) * 1000) if self.completed_at else 0,
        }


@dataclass
class OrchestratorEvent:
    type: str
    data: dict = field(default_factory=dict)


# Agent system prompts
_AGENT_PROMPTS = {
    "coder": "You are DASH Coder. Write clean, production-ready code with type hints and error handling. Show code first, explain briefly.",
    "researcher": "You are DASH Researcher. Analyze, compare, and summarize. Give clear recommendations.",
    "executor": "You are DASH Executor. Give exact commands, expected output, and prerequisites.",
    "verifier": "You are DASH Verifier. Check correctness, edge cases, security. Give pass/fail with specific issues.",
    "planner": "You are DASH Planner. Break goals into concrete actionable steps with dependencies.",
}


class Orchestrator:
    """Chains agents via cloud AI for fast complex task execution."""

    def __init__(self):
        self._active: dict[str, bool] = {}

    async def run(
        self, task: str, context: dict[str, Any] | None = None,
        max_steps: int = 8,
    ) -> AsyncIterator[OrchestratorEvent]:
        run_id = str(uuid.uuid4())[:12]
        self._active[run_id] = True

        try:
            # ── Plan ───────────────────────────────────────
            yield OrchestratorEvent(type="status", data={"status": "planning", "message": "Planning..."})

            steps = await self._plan(task, max_steps)
            yield OrchestratorEvent(type="plan", data={"run_id": run_id, "steps": [s.to_dict() for s in steps], "total": len(steps)})

            ctx = f"Task: {task}\n"

            # ── Execute steps ──────────────────────────────
            for step in steps:
                if not self._active.get(run_id):
                    yield OrchestratorEvent(type="cancelled", data={"run_id": run_id})
                    break

                step.status = StepStatus.RUNNING
                step.started_at = time.time()
                yield OrchestratorEvent(type="step_start", data={"step": step.to_dict()})

                try:
                    agent = step.step_type.value if step.step_type != StepType.PLAN else "planner"
                    result = await self._call_agent(agent, step.description, ctx)
                    step.agent = agent
                    step.result = result
                    step.status = StepStatus.COMPLETED
                    step.completed_at = time.time()
                    ctx += f"\n[{step.step_type.value}] {step.description}\nResult: {result[:1500]}\n"
                    yield OrchestratorEvent(type="step_done", data={"step": step.to_dict()})
                except Exception as exc:
                    step.status = StepStatus.FAILED
                    step.error = str(exc)
                    step.completed_at = time.time()
                    yield OrchestratorEvent(type="step_error", data={"step": step.to_dict()})

            # ── Summary ────────────────────────────────────
            completed = sum(1 for s in steps if s.status == StepStatus.COMPLETED)
            summary = await self._summarize(task, steps, ctx)

            yield OrchestratorEvent(type="complete", data={
                "run_id": run_id, "summary": summary,
                "completed": completed, "failed": len(steps) - completed,
                "total": len(steps), "steps": [s.to_dict() for s in steps],
            })

        except Exception as exc:
            logger.exception("Orchestrator failed: %s", exc)
            yield OrchestratorEvent(type="error", data={"error": str(exc)})
        finally:
            self._active.pop(run_id, None)

    def cancel(self, run_id: str):
        self._active[run_id] = False

    # ── Private ────────────────────────────────────────────

    async def _plan(self, task: str, max_steps: int) -> list[OrchestratorStep]:
        prompt = f"""Decompose into {max_steps} or fewer steps. JSON only, no markdown:
{{"steps":[{{"description":"...","type":"plan|code|research|execute|verify"}}]}}

Task: {task}"""

        response = await self._call_llm([{"role": "user", "content": prompt}])
        return self._parse_plan(response, task, max_steps)

    def _parse_plan(self, response: str, task: str, max_steps: int) -> list[OrchestratorStep]:
        try:
            match = re.search(r'\{[\s\S]*"steps"[\s\S]*\}', response)
            data = json.loads(match.group()) if match else json.loads(response)
        except (json.JSONDecodeError, AttributeError):
            return [OrchestratorStep(str(uuid.uuid4())[:8], 0, task, StepType.EXECUTE)]

        steps = []
        for i, s in enumerate(data.get("steps", [])[:max_steps]):
            try:
                st = StepType(s.get("type", "plan").lower())
            except ValueError:
                st = StepType.PLAN
            steps.append(OrchestratorStep(str(uuid.uuid4())[:8], i, s.get("description", f"Step {i+1}"), st))
        return steps or [OrchestratorStep(str(uuid.uuid4())[:8], 0, task, StepType.EXECUTE)]

    async def _call_agent(self, agent: str, description: str, context: str) -> str:
        system = _AGENT_PROMPTS.get(agent, _AGENT_PROMPTS["planner"])
        prompt = f"{description}\n\nContext:\n{context[-2000:]}"
        return await self._call_llm([
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ])

    async def _call_llm(self, messages: list[dict], timeout: float = 30.0) -> str:
        from dash_backend.llm.cloud_call import cloud_chat
        try:
            return await asyncio.wait_for(cloud_chat(messages, timeout=timeout), timeout=timeout + 5)
        except Exception:
            from dash_backend.llm.service import collect_streamed_response
            return await asyncio.wait_for(collect_streamed_response(messages), timeout=90.0)

    async def _summarize(self, task: str, steps: list[OrchestratorStep], ctx: str) -> str:
        steps_txt = "\n".join(f"[{s.step_type.value}] {s.description} → {s.status.value}" for s in steps)
        return await self._call_llm([{"role": "user", "content": f"Summarize in 2-3 sentences:\nTask: {task}\nSteps:\n{steps_txt}"}], timeout=15)


_orchestrator: Orchestrator | None = None

def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
