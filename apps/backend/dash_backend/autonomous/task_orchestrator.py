"""Task orchestrator — persistent complex-goal execution (decisions.md #90).

Turns a goal into a validated dependency graph of tool-backed steps and runs
it to completion with: permission-gated confirmations, deterministic
verification, bounded retries with recovery, pause/resume/cancel, and
checkpoint persistence that survives restarts.

Architecture (all control flow deterministic; the LLM only plans and picks
tools — never enforces policy):

    create_task ──► plan_task_graph ──► run_ready_steps (waves)
                          │                     │
                          ▼                     ▼
                    AgentTask (persisted)  _run_step
                                                │
                                    ┌───────────┼───────────┐
                                    ▼           ▼           ▼
                             confirm gate   tool exec   verify_step
                                    │           │           │
                                    └─────► retry/recover ──┘
                                                │
                                        finalize → report
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Callable

from dash_backend.logging_config import get_logger

from dash_backend.autonomous.task_graph import run_ready_steps, validate_graph
from dash_backend.autonomous.task_planner import plan_task_graph
from dash_backend.autonomous.task_policy import classify_risk, sanitize_untrusted
from dash_backend.autonomous.task_state import (
    AgentTask,
    RiskLevel,
    StepStatus,
    TaskStateStore,
    TaskStatus,
    TaskStep,
)
from dash_backend.autonomous.task_verifier import VerificationStatus, verify_step

logger = get_logger(__name__)

TOOL_TIMEOUT = 120.0
SELECT_TIMEOUT = 45.0
TASK_TIMEOUT = 1800.0  # hard wall-clock cap per task
MAX_CONCURRENT_TASKS = 3


def _task_model() -> str | None:
    """Model for structured task work (planning/tool-choice) — spec #26.

    The persona chat model (dash-finetuned) is tuned for conversation and is
    unreliable at strict JSON. A JSON-capable instruct model can be pinned
    via DASH_TASK_MODEL; a sensible default is picked from what Ollama
    actually has installed (never a blind guess: verify at call time).
    """
    import os
    return os.environ.get("DASH_TASK_MODEL") or None


# Path extraction for deterministic arg prefill. Three shapes, most
# specific first: Windows drive paths, slash-joined relative paths
# (sandbox-relative tools like create_file/write_file take these), and
# bare filenames with a known extension ("dash_demo_report.txt").
_PATH_RE = re.compile(r'[A-Za-z]:[/\\][^\s",;()’"]+')
_REL_PATH_RE = re.compile(r'\b[\w.-]+(?:[/\\][\w.-]+)+\b')
_FILENAME_RE = re.compile(
    r"\b[\w-]+\.(?:txt|md|json|csv|log|py|ts|tsx|js|ya?ml|html|css|ini|cfg)\b"
)
# Bare directory name: "the directory to_delete_demo", "folder named demo",
# "directory called X" — no slashes/extension, so the other regexes miss it.
_DIR_NAME_RE = re.compile(
    r'\b(?:directory|folder)\s+(?:named\s+|called\s+)?[\"\']?([\w.-]+)', re.IGNORECASE
)


def _extract_paths(text: str) -> list[str]:
    """Concrete path-like tokens, longest-first (longest = most specific)."""
    found: list[str] = []
    for rx in (_PATH_RE, _REL_PATH_RE, _FILENAME_RE, _DIR_NAME_RE):
        for m in rx.findall(text or ""):
            if m and m not in found:
                found.append(m)
    found.sort(key=len, reverse=True)
    return found


_FOLDER_TOOLS = ("folder", "directory", "dir", "browse", "list")


def _looks_like_file(path: str) -> bool:
    from pathlib import Path as _P
    return bool(_P(path).suffix)


def _heuristic_arg(param: str, tool: str, description: str,
                   goal: str = "") -> str | None:
    """Fill a required path-like arg from the step description, falling back
    to paths mentioned in the GOAL itself (planners sometimes write vague
    step descriptions while the goal carries the concrete path)."""
    paths = _extract_paths(description) or _extract_paths(goal)
    if not paths:
        return None
    wants_folder = any(w in tool for w in _FOLDER_TOOLS)
    if wants_folder:
        folders = [p for p in paths if not _looks_like_file(p)] or paths
        return max(folders, key=len).rstrip("\\/")
    files = [p for p in paths if _looks_like_file(p)] or paths
    return max(files, key=len)


class TaskOrchestrator:
    def __init__(self, store: TaskStateStore | None = None):
        self._store = store or TaskStateStore()
        self._tasks: dict[str, AgentTask] = self._store.load_all()
        self._running: dict[str, asyncio.Task] = {}
        self._callbacks: list[Callable] = []

    # ── Event plumbing ────────────────────────────────────────────────

    def on_event(self, callback: Callable) -> Callable:
        self._callbacks.append(callback)

        def _unsubscribe() -> None:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass
        return _unsubscribe

    def _push(self, task: AgentTask, event: str, extra: dict[str, Any] | None = None) -> None:
        task.record_event(event, json.dumps(extra or {}, default=str)[:200])
        task.touch()
        self._store.save_all(self._tasks)
        payload = {"type": f"task.{event}", "task": task.to_dict()}
        if extra:
            payload.update(extra)
        from dash_backend.autonomous.task_push import push_task_event
        push_task_event(task.user_id, payload)
        self._claim_presence(task)
        # Immediate owner contact for owner-relevant events (decisions.md
        # #124): the ws push above is best-effort and invisible with no
        # client connected; failures, recovery, and confirmation gates go
        # through the shared #119 urgency routing so they reach the owner
        # even without a live desktop session. Fire-and-forget — owner
        # contact must never break or delay task execution.
        if event in ("failed", "recovery", "waiting_confirmation"):
            try:
                import os as _os

                from dash_backend.assistant import proactive as _proactive
                notifier = None
                audit = None
                # Test/headless quietness: the desktop notifier spawns a
                # real PowerShell toast and the audit service writes JSONL
                # to disk — neither may fire under pytest (or with
                # DASH_DISABLE_DESKTOP_TOASTS=1); ws/phone routing still
                # runs, so owner contact stays observable in tests.
                if ("PYTEST_CURRENT_TEST" not in _os.environ
                        and _os.getenv("DASH_DISABLE_DESKTOP_TOASTS") != "1"):
                    from dash_backend.services.audit_logs import get_audit_service
                    from dash_backend.services.notifications import NotificationService
                    notifier = NotificationService()
                    audit = get_audit_service()
                asyncio.ensure_future(_proactive.notify_task_event(
                    task.to_dict(), event,
                    audit=audit,
                    notifier=notifier,
                ))
            except Exception:
                logger.exception("task owner-contact scheduling failed")
        for cb in list(self._callbacks):
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.ensure_future(cb(event, task.to_dict()))
                else:
                    cb(event, task.to_dict())
            except Exception:
                pass

    def _claim_presence(self, task: AgentTask) -> None:
        """Mirror task state into the presence engine (decisions.md #116):
        the orchestrator's honest task status IS a presence claim — mapped
        1:1, never fabricated. Released when no active tasks remain."""
        try:
            from dash_backend.assistant.presence import get_presence_engine
            engine = get_presence_engine()
            status_to_state = {
                "running": "executing",
                "planning": "thinking",
                "verifying": "verifying",
                "recovering": "recovering",
                "waiting_confirmation": "waiting_for_approval",
                "paused": "paused",
                "completed": None,
                "failed": None,
                "cancelled": None,
                "pending": "monitoring",
            }
            state = status_to_state.get(getattr(task.status, "value", str(task.status)))
            if state is None:
                # Terminal task: check whether any other task is still active.
                active = [t for t in self._tasks.values()
                          if getattr(t.status, "value", str(t.status))
                          not in ("completed", "failed", "cancelled")]
                if not active:
                    engine.release("task_orchestrator")
                return
            detail = f"{getattr(task.status, 'value', task.status)}: {task.goal[:80]}"
            same_status = [t for t in self._tasks.values()
                           if t.id != task.id and t.status == task.status]
            if same_status:
                detail = f"[{len(same_status) + 1} active] " + detail
            engine.claim("task_orchestrator", state, detail=detail)
        except Exception:
            # Presence is observability, never execution-critical.
            pass

    # ── Queries ───────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> AgentTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in sorted(
            self._tasks.values(), key=lambda t: t.created_at, reverse=True
        )]

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def create_task(
        self, goal: str, user_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AgentTask:
        from dash_backend.autonomous.candor import refusal_for
        refusal = refusal_for(goal)
        if refusal:
            raise ValueError(refusal)

        running = [t for t in self._tasks.values()
                   if t.status in (TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.VERIFYING)]
        if len(running) >= MAX_CONCURRENT_TASKS:
            raise ValueError(
                f"{len(running)} tasks already running (max {MAX_CONCURRENT_TASKS}) — pause or cancel one first"
            )

        task = AgentTask(goal=goal, user_id=user_id)
        task.status = TaskStatus.PLANNING
        self._tasks[task.id] = task
        self._push(task, "created")
        self._running[task.id] = asyncio.create_task(self._plan_and_run(task))
        self._running[task.id].add_done_callback(
            lambda t: self._running.pop(task.id, None)
        )
        return task

    async def _plan_and_run(self, task: AgentTask) -> None:
        try:
            planned = await plan_task_graph(task.goal, {"user_id": task.user_id})
            task.steps = planned.steps
            validate_graph(task)
            self._push(task, "plan_ready", {"steps": [s.to_dict() for s in task.steps]})
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            await self._execute_task(task)
        except asyncio.CancelledError:
            self._store.save_all(self._tasks)
            raise
        except Exception as exc:
            logger.exception("Task %s planning/execution failed", task.id)
            task.status = TaskStatus.FAILED
            task.completed_at = time.time()
            task.final_report = {"goal": task.goal, "error": str(exc)}
            self._push(task, "failed", {"error": str(exc)})

    async def _execute_task(self, task: AgentTask) -> None:
        try:
            while True:
                if task.status in (TaskStatus.PAUSED, TaskStatus.CANCELLED):
                    return  # resume/approval relaunches this coroutine
                if time.time() - task.created_at > TASK_TIMEOUT:
                    task.status = TaskStatus.FAILED
                    task.completed_at = time.time()
                    task.final_report = {"goal": task.goal, "error": "task timed out"}
                    self._push(task, "failed", {"error": "task timed out"})
                    return
                ok = await run_ready_steps(task, self._run_step)
                awaiting = [s for s in task.steps
                            if s.status == StepStatus.AWAITING_CONFIRMATION]
                if awaiting:
                    # Blocked on the user. Each gated step owns its own
                    # confirmation (decisions.md #91) so parallel gates never
                    # overwrite each other; the oldest open gate is mirrored
                    # to task.pending_confirmation for REST/WS consumers.
                    self._sync_confirmation(task)
                    return  # approval relaunches this coroutine
                if ok:
                    self._finalize(task)
                    return
                # Some steps failed but others may still be runnable
                from dash_backend.autonomous.task_graph import cascade_blocked, ready_steps
                cascade_blocked(task)
                if not ready_steps(task):
                    self._finalize(task)
                    return
                self._push(task, "recovery", {"detail": "continuing after failed steps"})
        except asyncio.CancelledError:
            # pause/cancel: leave non-terminal steps honestly pending
            for s in task.steps:
                if s.status == StepStatus.RUNNING:
                    s.status = StepStatus.PENDING
                    s.error = "interrupted"
            self._store.save_all(self._tasks)
            raise

    def _sync_confirmation(self, task: AgentTask) -> None:
        """Mirror the OLDEST open confirmation gate for REST/WS consumers.

        Gates are owned per-step; the task-level pending_confirmation is a
        derived view (which approval the user is being asked for first),
        never the source of truth."""
        open_gates = [s for s in task.steps
                      if s.status == StepStatus.AWAITING_CONFIRMATION and s.confirmation]
        if open_gates:
            oldest = min(open_gates, key=lambda s: s.confirmation.get("requested_at", 0.0))
            task.pending_confirmation = dict(oldest.confirmation)
            task.status = TaskStatus.WAITING_CONFIRMATION
        else:
            task.pending_confirmation = None

    def _finalize(self, task: AgentTask) -> None:
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return
        completed = [s for s in task.steps if s.status == StepStatus.COMPLETED]
        failed = [s for s in task.steps if s.status == StepStatus.FAILED]
        skipped = [s for s in task.steps if s.status == StepStatus.SKIPPED]
        pending = [s for s in task.steps if s.status in (StepStatus.PENDING, StepStatus.BLOCKED)]
        unverified = [s for s in completed if s.verification.status != VerificationStatus.VERIFIED]
        # Honesty: pending steps at finalize time mean they never ran —
        # a task with unexecuted steps is NOT complete.
        ok = not failed and not skipped and not pending
        task.status = TaskStatus.COMPLETED if ok else TaskStatus.FAILED
        task.completed_at = time.time()
        task.final_report = {
            "goal": task.goal,
            "status": task.status.value,
            "completed_steps": [s.description for s in completed],
            "failed_steps": [{"step": s.description, "error": (s.error or "")[:300]} for s in failed],
            "skipped_steps": [s.description for s in skipped],
            "unverified_steps": [s.description for s in unverified],
            "not_executed_steps": [s.description for s in pending],
            "attempts": {s.id: s.attempts for s in task.steps if s.attempts > 1},
        }
        self._push(task, "completed" if ok else "failed", {
            "report": task.final_report,
        })

    # ── One step: gate → execute → verify → retry ─────────────────────

    async def _run_step(self, task: AgentTask, step: TaskStep) -> bool:
        # Confirmation gate (application-enforced; the LLM cannot pass it).
        # State lives on the STEP: parallel waves each own their gate.
        if step.risk == RiskLevel.HIGH and not (
            step.confirmation and step.confirmation.get("approved")
        ):
            step.status = StepStatus.AWAITING_CONFIRMATION
            step.confirmation = {
                "step_id": step.id,
                "tool": step.tool,
                "args": step.args,
                "description": step.description,
                "risk": step.risk.value,
                "requested_at": time.time(),
                "approved": False,
            }
            task.status = TaskStatus.WAITING_CONFIRMATION
            self._sync_confirmation(task)
            self._push(task, "waiting_confirmation", {
                "step": step.to_dict(),
                "message": f"Approval required: {step.description} (tool: {step.tool or 'LLM choice'}, risk: high)",
            })
            return True  # step stays open, not failed; run loop exits

        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        task.current_step_id = step.id
        # Approval bookkeeping from a previous WAITING_CONFIRMATION round —
        # read from THIS step's own gate: "approved" = the user approved this
        # step while it was gated before execution; "confirmed_result" = the
        # tool's own CONFIRM gate already finished with the user's approval
        # and its result waits here. Consumed once.
        snap = step.confirmation or {}
        pre_approved = bool(snap.get("approved"))
        pre_result: dict[str, Any] | None = None
        if pre_approved and "confirmed_result" in snap:
            pre_result = snap["confirmed_result"]
        step.confirmation = None
        self._push(task, "step_started", {"step": step.to_dict()})

        last_result: dict[str, Any] | None = pre_result
        verified = False
        for attempt in range(1, max(1, step.max_attempts) + 1):
            step.attempts = attempt
            if pre_result is not None and attempt == 1:
                # Approval already finished the tool's pending execution
                # (approve_step → confirm_execution). Replay that result —
                # the tool must NOT run a second time.
                verification = await verify_step(step, last_result)
                step.verification = verification
                if verification.status == VerificationStatus.VERIFIED:
                    verified = True
                else:
                    step.error = verification.detail
                break
            tool, args = await self._resolve_tool(task, step, attempt, last_result)
            if tool is None:
                step.error = "no suitable tool found"
                if attempt < max(1, step.max_attempts):
                    # Retry: the repair round re-selects with the failure in view
                    await asyncio.sleep(min(2 ** attempt, 8))
                    continue
                break
            # Policy re-check at execution time — chosen tool is reclassified;
            # a HIGH tool chosen at the last moment still hits the gate.
            if classify_risk(tool) == "high" and step.risk != RiskLevel.HIGH:
                step.risk = RiskLevel.HIGH
                step.status = StepStatus.PENDING
                return await self._run_step(task, step)

            last_result = await self._execute_tool(tool, args)

            # The tool itself declared CONFIRM and returned a pending token —
            # DASH's existing confirmation rules (spec #10) are honored: the
            # step gates on the user, the token is finished via
            # confirm_execution AFTER approval, never counted as success.
            if (
                isinstance(last_result, dict)
                and last_result.get("status") == "pending_confirmation"
                and last_result.get("confirmation_token")
            ):
                token = last_result["confirmation_token"]
                if pre_approved:
                    # The user approved this exact step moments ago (pre-
                    # execution gate). Finish the tool's own pending token
                    # now instead of asking twice for the same action —
                    # one approval, one execution, still application-gated.
                    try:
                        from dash_backend.tools.tool_manager import get_tool_manager
                        final: dict[str, Any] | None = None
                        async for _evt, data in get_tool_manager().confirm_execution(token):
                            final = data
                        last_result = final or {"error": "confirmed execution produced no result"}
                    except Exception as exc:
                        last_result = {"error": f"confirmation execution failed: {exc}"}
                    verification = await verify_step(step, last_result)
                    step.verification = verification
                    if verification.status == VerificationStatus.VERIFIED:
                        verified = True
                        break
                    if attempt < step.max_attempts:
                        step.error = verification.detail
                        continue
                    break
                step.status = StepStatus.AWAITING_CONFIRMATION
                step.confirmation = {
                    "step_id": step.id,
                    "tool": tool,
                    "args": args,
                    "description": step.description,
                    "risk": step.risk.value,
                    "requested_at": time.time(),
                    "approved": False,
                    "tool_token": token,
                }
                task.status = TaskStatus.WAITING_CONFIRMATION
                self._sync_confirmation(task)
                self._push(task, "waiting_confirmation", {
                    "step": step.to_dict(),
                    "message": f"Tool '{tool}' requires your confirmation to proceed.",
                })
                return True  # step stays open; approval relaunches

            verification = await verify_step(step, last_result)
            step.verification = verification
            if verification.status == VerificationStatus.VERIFIED:
                verified = True
                break
            if attempt < step.max_attempts:
                # Schema-repair recovery: "Missing required parameter" means
                # the step's args don't match the tool's real schema — the
                # next attempt re-selects WITH the missing names in view.
                result_text = json.dumps(last_result, default=str)
                if "Missing required parameter" in result_text:
                    from dash_backend.tools.tool_manager import get_tool_manager
                    step._missing_params = self._missing_required_params(
                        get_tool_manager(), tool, args
                    )
                step.error = verification.detail
                self._push(task, "recovery", {
                    "step": step.id, "attempt": attempt,
                    "detail": f"retrying after: {verification.detail}",
                })
                await asyncio.sleep(min(2 ** attempt, 8))

        step.completed_at = time.time()
        step.result_summary = sanitize_untrusted(
            json.dumps(last_result, default=str), 300
        ) if last_result else None
        if verified:
            step.status = StepStatus.COMPLETED
            self._push(task, "step_completed", {"step": step.to_dict()})
            return True
        step.status = StepStatus.FAILED
        step.error = step.verification.detail or step.error or "verification failed"
        self._push(task, "step_failed", {"step": step.to_dict()})
        return False

    async def _resolve_tool(
        self, task: AgentTask, step: TaskStep, attempt: int,
        last_result: dict[str, Any] | None,
    ) -> tuple[str | None, dict[str, Any]]:
        """Plan-declared tool, or LLM tool selection for open steps."""
        if step.tool:
            return step.tool, step.args
        missing = getattr(step, "_missing_params", None)
        # Observation (decisions.md #90 spec #12): results of completed
        # dependency steps inform tool choice and args — e.g. a folder
        # listing supplies the exact paths the next step needs.
        dep_context = "\n".join(
            f"[{s.description[:80]}] {sanitize_untrusted(s.result_summary, 350)}"
            for s in task.steps
            if s.id in step.depends_on and s.status == StepStatus.COMPLETED and s.result_summary
        )
        if attempt > 1 and last_result is not None:
            # Recovery: re-select with the failure and any missing params in view
            step_args = dict(step.args)
            step_args["_previous_failure"] = sanitize_untrusted(
                json.dumps(last_result, default=str), 400
            )
            return await self._llm_select_tool(
                task, step, step_args, missing_params=missing, dep_context=dep_context,
            )
        return await self._llm_select_tool(
            task, step, step.args, missing_params=missing, dep_context=dep_context,
        )

    async def _llm_select_tool(
        self, task: AgentTask, step: TaskStep, args: dict[str, Any],
        missing_params: list[str] | None = None,
        dep_context: str = "",
    ) -> tuple[str | None, dict[str, Any]]:
        """LLM picks a real registered tool + args, guided by the tool's REAL
        parameter schema. ``missing_params`` feeds a repair round after a
        "Missing required parameter" failure."""
        from dash_backend.llm.service import build_chat_messages, collect_streamed_response
        from dash_backend.tools.tool_manager import get_tool_manager

        manager = get_tool_manager()
        try:
            defs = manager.select_tool_definitions(step.description, max_tools=10)
        except Exception:
            defs = []
        lines: list[str] = []
        for td in defs:
            fn = td.get("function", td)
            name = fn.get("name", "")
            if not name:
                continue
            params = fn.get("parameters", {}) or {}
            req = params.get("required", []) or []
            props = params.get("properties", {}) or {}
            sig = ", ".join(
                f"{k}: {props.get(k, {}).get('type', '?')}{' REQUIRED' if k in req else ''}"
                for k in list(req) + [k for k in props if k not in req]
            )
            desc = (fn.get("description", "") or "")[:100]
            lines.append(f"- {name}({sig}) — {desc}")
        repair_note = ""
        if missing_params:
            repair_note = (
                f"\nPREVIOUS ATTEMPT FAILED. These required parameters were missing: "
                f"{missing_params}. You MUST supply a value for each."
            )
        obs_note = ""
        if dep_context.strip():
            obs_note = f"\nRESULTS OF PREVIOUS STEPS (use these facts for exact paths/values):\n{dep_context}"
        paths_hint = ""
        mentioned = _extract_paths(step.description)
        if mentioned:
            paths_hint = f"\nPATHS MENTIONED IN THIS STEP (copy them EXACTLY into args): {mentioned}"
        prompt = (
            f"GOAL: {task.goal}\nSTEP: {step.description}\n"
            f"AVAILABLE TOOLS (with exact parameter names):\n" + "\n".join(lines) + "\n"
            f"ARGS HINT: {json.dumps(args, default=str)[:300]}"
            f"{obs_note}"
            f"{paths_hint}"
            f"{repair_note}\n"
            'Respond ONLY with JSON: {"tool": "name", "args": {}}'
        )
        try:
            raw = await asyncio.wait_for(
                collect_streamed_response(
                    build_chat_messages(
                        system_prompt=(
                            "You choose tools for DASH. Use the EXACT parameter names shown. "
                            "Respond ONLY with the JSON object."
                        ),
                        user_message=prompt,
                    ),
                    model=_task_model(),
                ),
                timeout=SELECT_TIMEOUT,
            )
            data = json.loads(raw.strip().strip("`"))
            tool = data.get("tool")
            if tool and manager.get_tool(tool):
                merged = dict(args)
                merged.update(data.get("args", {}) or {})
                merged.pop("_previous_failure", None)
                # Deterministic arg prefill (spec #3): the planner already
                # wrote concrete paths into the step description (or the goal
                # did) — a 1B model reliably picks the TOOL but is unreliable
                # at transcribing paths, so application code fills what it
                # omitted.
                for p in self._missing_required_params(manager, tool, merged):
                    if heur := _heuristic_arg(p, tool, step.description, task.goal):
                        merged[p] = heur
                return tool, merged
        except Exception as exc:
            logger.debug("LLM tool selection failed for step %s: %s", step.id, exc)
        return None, {}

    @staticmethod
    def _missing_required_params(manager: Any, tool: str, args: dict[str, Any]) -> list[str]:
        """Which of the tool's declared required parameters are absent/empty."""
        try:
            t = manager.get_tool(tool)
            if t is None:
                return []
            missing = []
            for p in (t.spec.parameters or []):
                if getattr(p, "required", False):
                    v = args.get(p.name)
                    if v is None or (isinstance(v, str) and not v.strip()):
                        missing.append(p.name)
            return missing
        except Exception:
            return []

    async def _execute_tool(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        from dash_backend.tools.base_tool import ToolContext
        from dash_backend.tools.tool_manager import get_tool_manager

        manager = get_tool_manager()
        try:
            return await asyncio.wait_for(
                manager.execute(tool, args, ToolContext(user_id="task_orchestrator")),
                timeout=TOOL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return {"error": f"tool '{tool}' timed out after {TOOL_TIMEOUT:.0f}s"}
        except Exception as exc:
            return {"error": f"tool '{tool}' failed: {exc}"}

    # ── Confirmation / pause / resume / cancel ────────────────────────

    async def approve_step(
        self, task_id: str, approved: bool, step_id: str | None = None,
    ) -> bool:
        """Resolve the user's decision on an open confirmation gate.

        Targets ``step_id`` explicitly when given (decisions.md #91 — each
        step owns its own gate); defaults to the OLDEST open gate, which is
        what ``pending_confirmation`` mirrors to REST/WS consumers. Pending
        tool tokens are finished/rejected through DASH's existing machinery;
        approval replays the confirmed result instead of re-executing."""
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.WAITING_CONFIRMATION:
            return False
        open_gates = [s for s in task.steps
                      if s.status == StepStatus.AWAITING_CONFIRMATION and s.confirmation]
        if step_id:
            step = next((s for s in open_gates if s.id == step_id), None)
        else:
            step = (
                min(open_gates, key=lambda s: s.confirmation.get("requested_at", 0.0))
                if open_gates else None
            )
        snap = (step.confirmation or {}) if step is not None else {}
        if step is not None:
            step.confirmation = None
        for g in open_gates:
            if g is not step:
                g.confirmation["approved"] = False
        task.status = TaskStatus.RUNNING
        if step is None:
            self._sync_confirmation(task)
            self._push(task, "recovery", {"detail": "confirmation resolved; step missing"})
            return True
        tool_token = snap.get("tool_token")
        if approved:
            if tool_token:
                # Finish the tool's own pending execution through DASH's
                # existing confirmation machinery — no second execution of
                # the tool side effects, the confirmed result is replayed.
                try:
                    from dash_backend.tools.tool_manager import get_tool_manager
                    final: dict[str, Any] | None = None
                    async for _evt, data in get_tool_manager().confirm_execution(tool_token):
                        final = data
                    snap["confirmed_result"] = final
                except Exception as exc:
                    snap["confirmed_result"] = {"error": f"confirmation execution failed: {exc}"}
            snap["approved"] = True
            step.confirmation = snap  # one-shot approval proof on the step
            step.status = StepStatus.PENDING
            self._push(task, "resumed", {"step": step.to_dict(), "approved": True})
        else:
            if tool_token:
                try:
                    from dash_backend.tools.tool_manager import get_tool_manager
                    await get_tool_manager().reject_execution(tool_token)
                except Exception:
                    pass
            step.status = StepStatus.SKIPPED
            step.error = "rejected by user"
            self._push(task, "resumed", {"step": step.to_dict(), "approved": False})
        self._sync_confirmation(task)
        self._relaunch(task)
        return True

    async def pause_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status not in (
            TaskStatus.PLANNING, TaskStatus.RUNNING,
            TaskStatus.VERIFYING, TaskStatus.WAITING_CONFIRMATION,
        ):
            return False
        # Pausing a waiting task revokes the pending approval request: the
        # awaiting step returns to PENDING so resume re-runs the gate —
        # an approval snapshot must never outlive the wait it was granted in.
        if task.status == TaskStatus.WAITING_CONFIRMATION:
            for s in task.steps:
                if s.status == StepStatus.AWAITING_CONFIRMATION and s.confirmation:
                    s.status = StepStatus.PENDING
                    s.confirmation = None
            task.pending_confirmation = None
        task.status = TaskStatus.PAUSED
        self._push(task, "paused")
        self._cancel_run(task)
        return True

    async def resume_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status != TaskStatus.PAUSED:
            return False
        task.status = TaskStatus.RUNNING
        self._push(task, "resumed")
        self._relaunch(task)
        return True

    async def cancel_task(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task or task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return False
        task.status = TaskStatus.CANCELLED
        task.completed_at = time.time()
        self._push(task, "cancelled")
        self._cancel_run(task)
        self._store.save_all(self._tasks)
        return True

    async def replan_task(self, task_id: str, instruction: str) -> bool:
        """Regenerate the remaining plan, preserving completed history."""
        task = self._tasks.get(task_id)
        if not task or task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED,
                                       TaskStatus.CANCELLED, TaskStatus.PLANNING):
            return False
        done_descs = [s.description for s in task.steps if s.status == StepStatus.COMPLETED]
        failed_descs = [f"{s.description} (failed: {(s.error or '')[:150]})" for s in task.steps
                        if s.status in (StepStatus.FAILED, StepStatus.SKIPPED)]
        revised_goal = (
            f"{task.goal}\n\nREPLAN REASON: {sanitize_untrusted(instruction, 400)}\n"
            f"ALREADY COMPLETED (do not redo): {done_descs}\n"
            f"KNOWN FAILURES: {failed_descs}"
        )
        planned = await plan_task_graph(revised_goal, {"user_id": task.user_id})
        offset = len(task.steps)
        for i, s in enumerate(planned.steps):
            s.id = f"r{offset + i}"
            s.index = offset + i
        task.steps.extend(planned.steps)
        task.status = TaskStatus.RUNNING
        self._push(task, "replanned", {"added_steps": len(planned.steps)})
        self._relaunch(task)
        return True

    # ── Restart recovery ──────────────────────────────────────────────

    def resume_interrupted(self) -> int:
        """Resume non-terminal tasks left running by a restart."""
        resumed = 0
        for task in self._tasks.values():
            if task.status in (TaskStatus.PLANNING, TaskStatus.RUNNING, TaskStatus.VERIFYING):
                for s in task.steps:
                    if s.status == StepStatus.RUNNING:
                        s.status = StepStatus.PENDING
                        s.error = "interrupted by restart"
                task.record_event("recovery", "resumed after restart")
                self._push(task, "resumed", {"detail": "resumed after restart"})
                self._relaunch(task)
                resumed += 1
        return resumed

    # ── Internals ─────────────────────────────────────────────────────

    def _relaunch(self, task: AgentTask) -> None:
        if task.id in self._running and not self._running[task.id].done():
            return
        self._running[task.id] = asyncio.create_task(self._execute_task(task))
        self._running[task.id].add_done_callback(
            lambda t: self._running.pop(task.id, None)
        )

    def _cancel_run(self, task: AgentTask) -> None:
        running = self._running.get(task.id)
        if running and not running.done():
            running.cancel()


_orchestrator: TaskOrchestrator | None = None


def get_task_orchestrator() -> TaskOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TaskOrchestrator()
    return _orchestrator
