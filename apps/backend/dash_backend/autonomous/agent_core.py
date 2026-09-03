"""Autonomous Agent Core — LLM-driven reasoning loop.

The agent operates in an observe → think → act cycle:
1. OBSERVE: Gather current state (system info, memory, task context)
2. THINK: Ask the LLM what to do next given the observation
3. ACT: Execute the chosen tool/action
4. REFLECT: Evaluate the result, update memory, decide next step

This repeats until the goal is achieved, max iterations hit, or the agent
decides it's done.  The LLM has access to the full tool registry and can
call any tool it has permission to use.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ── Limits ────────────────────────────────────────────────────────────────
MAX_ITERATIONS = 30          # hard cap per goal
DEFAULT_TIMEOUT = 300.0      # 5 minutes per goal
THINK_TIMEOUT = 90.0         # max seconds per LLM think step


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    ACTING = "acting"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


@dataclass
class AgentStep:
    """One step in the agent's reasoning chain."""
    iteration: int
    observation: str
    thought: str
    action: dict[str, Any] | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: str | None = None
    success: bool | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentGoal:
    """An autonomous goal for the agent to pursue."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    state: AgentState = AgentState.IDLE
    steps: list[AgentStep] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    completed_at: float = 0.0
    max_iterations: int = MAX_ITERATIONS
    timeout: float = DEFAULT_TIMEOUT
    priority: int = 0  # higher = more urgent
    goal_memory: list = field(default_factory=list)  # per-goal working memory

    @property
    def elapsed(self) -> float:
        if self.started_at == 0:
            return 0.0
        end = self.completed_at or time.time()
        return end - self.started_at

    @property
    def iteration(self) -> int:
        return len(self.steps)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "state": self.state.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "elapsed": round(self.elapsed, 1),
            "result": self.result,
            "error": self.error,
            "steps": [
                {
                    "iteration": s.iteration,
                    "thought": s.thought,
                    "tool_name": s.tool_name,
                    "tool_args": s.tool_args,
                    "tool_result": (s.tool_result[:500] + "...") if s.tool_result and len(s.tool_result) > 500 else s.tool_result,
                    "success": s.success,
                    "duration_ms": round(s.duration_ms, 1),
                }
                for s in self.steps
            ],
        }


# ── System prompt for the autonomous agent ────────────────────────────────

AGENT_SYSTEM_PROMPT = """You are DASH — an autonomous AI agent that operates a Windows computer.

You receive a GOAL and current OBSERVATION. You decide what to do next.

RULES:
1. Think step by step. One action per response.
2. You have access to tools. Pick the best tool for the current step.
3. If a tool fails, try a different approach.
4. When the goal is achieved, say DONE with a summary.
5. Never run destructive commands without good reason.
6. If stuck after 3 attempts, report the blocker.

RESPONSE FORMAT (strict JSON):
{
  "thought": "What I observe and what I plan to do next",
  "action": "tool_name" or "DONE" or "BLOCKED",
  "args": { ... },
  "reasoning": "Why this action"
}

If the goal is achieved:
{
  "thought": "The goal has been achieved.",
  "action": "DONE",
  "summary": "What was accomplished"
}

If you are stuck:
{
  "thought": "I've tried multiple approaches and cannot proceed because...",
  "action": "BLOCKED",
  "reason": "What's blocking progress"
}
"""


class AgentCore:
    """The autonomous agent brain.

    Receives goals, uses LLM to plan and execute steps via tools,
    reflects on results, and adapts its approach.
    """

    def __init__(self, max_concurrent_llm: int = 2):
        self._goals: dict[str, AgentGoal] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._callbacks: list[Callable] = []
        self._memory: list[dict[str, Any]] = []  # shared short-term memory
        self._plans: dict[str, Any] = {}  # goal_id -> TaskPlan
        self._llm_semaphore = asyncio.Semaphore(max_concurrent_llm)
        self._max_concurrent_llm = max_concurrent_llm

    def on_step(self, callback: Callable) -> Callable:
        """Register a callback for step completion. Returns an unsubscribe function."""
        self._callbacks.append(callback)

        def _unsubscribe():
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass
        return _unsubscribe

    async def _notify(self, event: str, data: dict) -> None:
        for cb in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event, data)
                else:
                    cb(event, data)
            except Exception:
                pass

    # ── Goal Management ────────────────────────────────────────────────

    def get_goal(self, goal_id: str) -> AgentGoal | None:
        return self._goals.get(goal_id)

    def list_goals(self) -> list[dict]:
        return [g.to_dict() for g in self._goals.values()]

    async def pause_goal(self, goal_id: str) -> bool:
        goal = self._goals.get(goal_id)
        if goal and goal.state in (AgentState.IDLE, AgentState.THINKING, AgentState.ACTING):
            goal.state = AgentState.PAUSED
            task = self._running_tasks.get(goal_id)
            if task and not task.done():
                task.cancel()
            return True
        return False

    async def cancel_goal(self, goal_id: str) -> bool:
        goal = self._goals.get(goal_id)
        if goal:
            goal.state = AgentState.FAILED
            goal.error = "Cancelled by user"
            goal.completed_at = time.time()
            task = self._running_tasks.get(goal_id)
            if task and not task.done():
                task.cancel()
            return True
        return False

    # ── Main Agent Loop ────────────────────────────────────────────────

    async def run_goal(
        self,
        description: str,
        context: dict[str, Any] | None = None,
        max_iterations: int = MAX_ITERATIONS,
        timeout: float = DEFAULT_TIMEOUT,
        priority: int = 0,
    ) -> AgentGoal:
        """Start executing a goal autonomously. Returns the goal object."""
        goal = AgentGoal(
            description=description,
            context=context or {},
            max_iterations=max_iterations,
            timeout=timeout,
            priority=priority,
        )
        self._goals[goal.id] = goal

        # Generate task plan for complex goals
        from dash_backend.autonomous.planner import is_complex_goal, plan_task
        if is_complex_goal(description):
            try:
                plan = await asyncio.wait_for(
                    plan_task(description, context),
                    timeout=30.0,
                )
                self._plans[goal.id] = plan
                logger.info(
                    "Task plan generated: %d steps for goal %s",
                    len(plan.steps), goal.id[:12],
                )
            except Exception as exc:
                logger.warning("Planner failed, proceeding without plan: %s", exc)

        task = asyncio.create_task(self._run_loop(goal))
        self._running_tasks[goal.id] = task
        task.add_done_callback(lambda t: self._running_tasks.pop(goal.id, None))

        logger.info("Agent goal started: %s — %s", goal.id, description[:80])
        return goal

    async def _run_loop(self, goal: AgentGoal) -> None:
        """The core observe → think → act → reflect loop."""
        goal.state = AgentState.THINKING
        goal.started_at = time.time()
        await self._notify("goal.started", {"goal": goal.to_dict()})

        try:
            while goal.iteration < goal.max_iterations:
                if goal.state == AgentState.PAUSED:
                    await self._notify("goal.paused", {"goal": goal.to_dict()})
                    return

                # ── OBSERVE ────────────────────────────────────────
                goal.state = AgentState.THINKING
                observation = await self._observe(goal)

                # Inject plan context if available
                plan = self._plans.get(goal.id)
                if plan and plan.current_step:
                    step_desc = plan.current_step.description
                    observation = (
                        f"CURRENT PLAN STEP ({plan.completed_count+1}/{len(plan.steps)}): "
                        f"{step_desc}\n\n"
                        f"{observation}"
                    )

                # ── THINK (semaphore-limited to avoid overwhelming LLM) ──
                async with self._llm_semaphore:
                    thought, action, args = await self._think(goal, observation)

                if action is None:
                    # LLM couldn't produce valid output
                    step = AgentStep(
                        iteration=goal.iteration + 1,
                        observation=observation[:1000],
                        thought=thought,
                    )
                    goal.steps.append(step)
                    continue

                # Check for DONE / BLOCKED
                if action.upper() == "DONE":
                    goal.state = AgentState.COMPLETED
                    goal.result = args.get("summary", thought)
                    goal.completed_at = time.time()
                    await self._notify("goal.completed", {"goal": goal.to_dict()})
                    logger.info("Agent goal completed: %s", goal.id)
                    try:
                        await self.remember(goal)
                    except Exception:
                        pass
                    return

                if action.upper() == "BLOCKED":
                    goal.state = AgentState.FAILED
                    goal.error = args.get("reason", thought)
                    goal.completed_at = time.time()
                    await self._notify("goal.failed", {"goal": goal.to_dict()})
                    logger.warning("Agent goal blocked: %s — %s", goal.id, goal.error)
                    try:
                        await self.remember(goal)
                    except Exception:
                        pass
                    return

                # ── ACT ────────────────────────────────────────────
                goal.state = AgentState.ACTING
                step = AgentStep(
                    iteration=goal.iteration + 1,
                    observation=observation[:1000],
                    thought=thought,
                    action={"tool": action, "args": args},
                    tool_name=action,
                    tool_args=args,
                )

                act_start = time.time()
                tool_result = await self._act(action, args or {})
                step.duration_ms = (time.time() - act_start) * 1000
                step.tool_result = str(tool_result)[:2000]
                step.success = not _is_error_result(tool_result)

                goal.steps.append(step)

                # Advance plan if this step succeeded
                if plan and plan.current_step and step.success:
                    plan.current_step.status = "done"
                    plan.current_step.result_summary = (step.tool_result or "")[:200]
                    if plan.current_step.index < len(plan.steps) - 1:
                        plan.steps[plan.current_step.index + 1].status = "active"
                    elif plan.is_complete:
                        goal.result = f"Plan completed: {plan.completed_count}/{len(plan.steps)} steps succeeded"

                # ── REFLECT ────────────────────────────────────────
                goal.state = AgentState.REFLECTING
                await self._reflect(goal, step)

                await self._notify("goal.step", {
                    "goal_id": goal.id,
                    "step": step.iteration,
                    "thought": thought,
                    "tool": action,
                    "success": step.success,
                })

                # Check timeout
                if goal.elapsed > goal.timeout:
                    goal.state = AgentState.FAILED
                    goal.error = f"Timed out after {goal.timeout}s"
                    goal.completed_at = time.time()
                    await self._notify("goal.failed", {"goal": goal.to_dict()})
                    return

            # Max iterations reached
            goal.state = AgentState.FAILED
            goal.error = f"Reached max iterations ({goal.max_iterations})"
            goal.completed_at = time.time()
            await self._notify("goal.failed", {"goal": goal.to_dict()})

        except asyncio.CancelledError:
            # Only overwrite state if not already PAUSED (pause sets state before cancelling)
            if goal.state != AgentState.PAUSED:
                goal.state = AgentState.FAILED
                goal.error = "Cancelled"
            goal.completed_at = time.time()
        except Exception as exc:
            logger.exception("Agent loop failed for goal %s", goal.id)
            goal.state = AgentState.FAILED
            goal.error = str(exc)
            goal.completed_at = time.time()
            await self._notify("goal.failed", {"goal": goal.to_dict()})

    # ── OBSERVE ────────────────────────────────────────────────────────

    async def _observe(self, goal: AgentGoal) -> str:
        """Gather current system state and context for the LLM."""
        parts = []

        # System info
        try:
            from dash_backend.services.system.system_info import get_system_info
            info = await asyncio.to_thread(get_system_info)
            cpu = info.get("cpu_percent", 0)
            ram = info.get("memory_percent", 0)
            parts.append(f"System: CPU={cpu}% RAM={ram}%")
        except Exception:
            parts.append("System: (metrics unavailable)")

        # Running processes (top 5)
        try:
            import psutil
            procs = []
            for p in sorted(psutil.process_iter(["pid", "name", "cpu_percent"]),
                             key=lambda x: x.info.get("cpu_percent", 0), reverse=True)[:5]:
                name = p.info.get("name", "?")
                cpu_p = p.info.get("cpu_percent", 0)
                procs.append(f"{name}({cpu_p}%)")
            parts.append(f"Top processes: {', '.join(procs)}")
        except Exception:
            pass

        # Goal context
        if goal.context:
            parts.append(f"Context: {json.dumps(goal.context)[:500]}")

        # Previous steps summary
        if goal.steps:
            recent = goal.steps[-3:]  # last 3 steps
            steps_summary = []
            for s in recent:
                status = "✓" if s.success else "✗"
                steps_summary.append(f"[{status}] {s.tool_name}: {s.thought[:100]}")
            parts.append(f"Recent steps: {'; '.join(steps_summary)}")

        # Per-goal working memory
        if goal.goal_memory:
            parts.append(f"Goal memory: {json.dumps(goal.goal_memory[-5:])[:500]}")
        # Shared memory from other goals (for context)
        elif self._memory:
            parts.append(f"System memory: {json.dumps(self._memory[-3:])[:300]}")

        return "\n".join(parts)

    # ── THINK ──────────────────────────────────────────────────────────

    async def _think(
        self, goal: AgentGoal, observation: str
    ) -> tuple[str, str | None, dict[str, Any] | None]:
        """Ask the LLM what to do next. Returns (thought, action, args)."""
        from dash_backend.llm.service import (
            build_chat_messages,
            chat_completion_with_native_tool_calls,
        )
        from dash_backend.tools.tool_manager import get_tool_manager

        # Build context messages
        steps_context = ""
        if goal.steps:
            steps_lines = []
            for s in goal.steps:
                status = "SUCCESS" if s.success else "FAILED"
                steps_lines.append(
                    f"Step {s.iteration}: {s.tool_name} → {status}\n"
                    f"  Thought: {s.thought}\n"
                    f"  Result: {(s.tool_result or '')[:200]}"
                )
            steps_context = "\n\nPREVIOUS STEPS:\n" + "\n".join(steps_lines)

        user_prompt = (
            f"GOAL: {goal.description}\n\n"
            f"CURRENT OBSERVATION:\n{observation}\n"
            f"{steps_context}\n\n"
            f"What should I do next? Respond with ONLY a JSON object."
        )

        # Get available tools for the LLM
        tool_manager = get_tool_manager()
        tool_defs = tool_manager.select_tool_definitions(
            goal.description, max_tools=15
        )

        # Convert tool defs to a readable summary for the prompt
        tool_names = []
        for td in tool_defs:
            fn = td.get("function", td)
            name = fn.get("name", "")
            desc = fn.get("description", "")[:80]
            tool_names.append(f"  - {name}: {desc}")

        tools_summary = "\n".join(tool_names)

        system_prompt = (
            f"{AGENT_SYSTEM_PROMPT}\n\n"
            f"AVAILABLE TOOLS:\n{tools_summary}\n\n"
            f"Respond with ONLY a JSON object. No markdown. No explanation."
        )

        messages = build_chat_messages(
            system_prompt=system_prompt,
            user_message=user_prompt,
        )

        try:
            # Use native tool calling but we parse the text response
            response = await asyncio.wait_for(
                chat_completion_with_native_tool_calls(
                    messages, tools=tool_defs[:15]
                ),
                timeout=THINK_TIMEOUT,
            )

            text = response.assistant_text.strip()

            # Try to parse as JSON
            thought, action, args = _parse_agent_response(text)

            # If the LLM used a tool call instead of text JSON
            if not action and response.tool_calls:
                tc = response.tool_calls[0]
                fn = tc.get("function", {})
                action = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                thought = f"Calling tool: {action}"

            return thought, action, args

        except asyncio.TimeoutError:
            logger.warning("Agent think step timed out after %ss", THINK_TIMEOUT)
            return f"LLM think timed out after {THINK_TIMEOUT}s", None, None
        except Exception as exc:
            logger.exception("Agent think step failed")
            return f"Error thinking: {exc}", None, None

    # ── ACT ────────────────────────────────────────────────────────────

    async def _act(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool and return the result."""
        from dash_backend.tools.tool_manager import get_tool_manager
        from dash_backend.tools.base_tool import ToolContext

        manager = get_tool_manager()
        tool = manager.get_tool(tool_name)

        if tool is None:
            # Try the command dispatch
            try:
                from dash_backend.api.routes.commands import execute_command
                return await execute_command(tool_name, args)
            except (ValueError, Exception) as exc:
                return {"error": f"Unknown tool: {tool_name} — {exc}"}

        context = ToolContext(user_id="autonomous_agent")
        try:
            result = await asyncio.wait_for(
                manager.execute(tool_name, args, context),
                timeout=60.0,
            )
            return result
        except asyncio.TimeoutError:
            return {"error": f"Tool '{tool_name}' timed out after 60s"}
        except Exception as exc:
            return {"error": f"Tool '{tool_name}' failed: {exc}"}

    # ── REFLECT ────────────────────────────────────────────────────────

    async def _reflect(self, goal: AgentGoal, step: AgentStep) -> None:
        """Evaluate the step result and update per-goal working memory."""
        entry = {
            "step": step.iteration,
            "tool": step.tool_name,
            "success": step.success,
            "thought": step.thought[:200],
            "result_summary": (step.tool_result or "")[:200],
        }
        goal.goal_memory.append(entry)

        # Keep per-goal memory bounded
        if len(goal.goal_memory) > 30:
            goal.goal_memory = goal.goal_memory[-20:]

        # Also store in shared memory (last 10 entries from all goals)
        self._memory.append({"goal": goal.id[:8], **entry})
        if len(self._memory) > 50:
            self._memory = self._memory[-30:]

        # If step failed, add a failure note
        if not step.success:
            goal.goal_memory.append({
                "type": "failure",
                "tool": step.tool_name,
                "error": (step.tool_result or "")[:200],
            })

    # ── Long-term Memory (Episodic) ────────────────────────────────────

    async def remember(self, goal: AgentGoal) -> None:
        """Store completed goal in long-term memory via the memory service."""
        try:
            from dash_backend.db.session import AsyncSessionLocal
            from dash_backend.intelligence.memory_service import MemoryService
            import uuid

            summary = (
                f"Autonomous task completed: {goal.description}\n"
                f"Status: {goal.state.value}\n"
                f"Iterations: {goal.iteration}\n"
                f"Result: {goal.result or goal.error}"
            )

            # Store as long-term memory
            svc = MemoryService()
            async with AsyncSessionLocal() as session:
                user_id = goal.context.get("user_id")
                if user_id:
                    try:
                        uid = uuid.UUID(user_id)
                        importance = 0.7 if goal.state == AgentState.COMPLETED else 0.3
                        await svc.store_long_term(
                            session, uid, summary,
                            memory_type="goal_outcome",
                            importance=importance,
                        )
                    except (ValueError, Exception):
                        pass
        except Exception as exc:
            logger.debug("Failed to store memory: %s", exc)

    def get_plan(self, goal_id: str) -> dict | None:
        plan = self._plans.get(goal_id)
        return plan.to_dict() if plan else None

    def get_status(self) -> dict[str, Any]:
        """Return overall agent status including concurrency info."""
        running = [g for g in self._goals.values() if g.state in (AgentState.THINKING, AgentState.ACTING, AgentState.REFLECTING)]
        queued = [g for g in self._goals.values() if g.state == AgentState.IDLE]
        completed = [g for g in self._goals.values() if g.state in (AgentState.COMPLETED, AgentState.FAILED)]
        return {
            "total_goals": len(self._goals),
            "running": len(running),
            "queued": len(queued),
            "completed": len(completed),
            "max_concurrent": self._max_concurrent_llm,
            "running_goals": [{"id": g.id[:12], "desc": g.description[:60], "state": g.state.value, "priority": g.priority} for g in running],
        }

    def get_working_memory(self) -> list[dict]:
        return list(self._memory)

    def clear_working_memory(self) -> None:
        self._memory.clear()


# ── Helpers ───────────────────────────────────────────────────────────────

def _parse_agent_response(text: str) -> tuple[str, str | None, dict | None]:
    """Parse the LLM's JSON response into (thought, action, args)."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text, None, None

    if not isinstance(data, dict):
        return text, None, None

    thought = data.get("thought", text)
    action = data.get("action")
    args = data.get("args", {})

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}

    return thought, action, args or {}


def _is_error_result(result: Any) -> bool:
    """Check if a tool result indicates an error."""
    if isinstance(result, dict):
        if "error" in result:
            return True
        status = result.get("status")
        if status in ("error", "failed"):
            return True
    return False


# ── Singleton ─────────────────────────────────────────────────────────────

_core: AgentCore | None = None


def get_agent_core() -> AgentCore:
    global _core
    if _core is None:
        _core = AgentCore()
    return _core
