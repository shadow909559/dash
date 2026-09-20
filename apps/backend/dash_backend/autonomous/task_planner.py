"""Graph planner — LLM proposes, application validates (decisions.md #90).

The LLM decomposes a goal into steps WITH dependencies, tool hints and
verification specs. Every field is then validated deterministically:
- risk is RECOMPUTED from the tool registry's declared permission policy —
  the model cannot promote a dangerous tool to 'safe' by declaring it;
- dependency cycles are broken by dropping back-edges;
- unknown tools keep tool=None (the orchestrator's LLM tool-selection at
  run time picks a real registered tool, which is then permission-checked);
- verify specs are type-checked against the verifier's supported set.

Fallback: if the LLM output is unusable, the plan degrades to the existing
linear ``plan_task`` shape — never a fabricated plan.
"""

from __future__ import annotations

import json
import re
from typing import Any

from dash_backend.logging_config import get_logger

from dash_backend.autonomous.task_policy import classify_risk
from dash_backend.autonomous.task_state import AgentTask, RiskLevel, TaskStep

logger = get_logger(__name__)

MAX_PLAN_STEPS = 12

VERIFY_TYPES = {"file_exists", "file_contains", "output_contains", "exit_code_zero", "http_ok", "none"}

def _real_tool_inventory() -> str:
    """The ACTUAL registered tools, for the planner prompt (decisions.md #91).

    A hand-written tool list drifts; the live run proved the model then
    invents steps for tools that don't exist ("search for an empty file to
    test"). The inventory comes from the registry so every step maps to a
    real capability — anything not listed cannot be planned.
    """
    lines: list[str] = []
    try:
        from dash_backend.tools.tool_manager import get_tool_manager
        manager = get_tool_manager()
        registry = getattr(manager, "_registry", None)
        tools = registry.get_all() if registry else {}
        for name, tool in list(tools.items())[:60]:
            desc = (getattr(tool, "description", "") or "")[:90]
            lines.append(f"- {name}: {desc}")
    except Exception:
        logger.exception("tool inventory unavailable; using static fallback")
        lines.append("- create_file: create a file at a path (path, content)")
        lines.append("- create_folder: create a directory at a path (path)")
        lines.append("- write_file: write content to a file (path, content)")
        lines.append("- read_file: read a file (path)")
        lines.append("- delete_directory: delete a directory recursively (path)")
        lines.append("- system_info: read system information ()")
    return "\n".join(lines)


PLANNER_GRAPH_PROMPT = """You are a task planner for DASH, an autonomous AI agent on Windows.

Given a GOAL, break it into concrete executable steps as a dependency graph.
Each step is executed by calling ONE existing tool (or by an LLM tool-choice
at run time when you set tool to null).

AVAILABLE TOOLS (the REAL registry — do not invent any others):
%s

RESPONSE FORMAT (strict JSON, no markdown):
{"steps": [
  {"id": "s1", "description": "...", "tool": "tool_name or null",
   "args": {}, "purpose": "...",
   "depends_on": ["ids of earlier steps this needs"],
   "risk": "safe|moderate|high (advisory only — policy recomputes it)",
   "verify": {"type": "file_exists|file_contains|output_contains|exit_code_zero|http_ok|none", ...}}
]}

RULES:
1. 2-6 steps — the SHORTEST plan that achieves the goal. No probe/test steps.
2. Every step must map to a tool FROM THE LIST ABOVE (or null for runtime choice).
3. Write concrete paths/filenames from the GOAL into the step description.
4. Verification-style steps must depend on the step they verify.
5. verify must be a real check that proves the step completed.
6. Return ONLY the JSON object.
""" % _real_tool_inventory()


# ── Deterministic fast-path (decisions.md #91, spec #4/#26) ──────────────
# Simple single-tool goals are planned by REGEX, never by the LLM. The live
# runs proved a 1B planner invents junk steps ("wait for the file to be
# created") that fail honestly and sink otherwise-successful tasks; a goal
# that names exactly one operation must produce exactly one step.

_FILE_GOAL = re.compile(
    r"create\s+(?:a\s+)?(?:new\s+)?(?:text\s+)?file\s+(?:named\s+)?"
    r"(?P<name>[\w.-]+\.[\w]+)\s+(?:inside|in)\s+(?:the\s+)?folder\s+"
    r"(?P<folder>[\w\\/.-]+)\s+containing\s+(?:the\s+line\s+)?"
    r"(?P<q>['\"])(?P<content>[^\'\"]+)['\"]",
    re.IGNORECASE,
)
_FOLDER_GOAL = re.compile(
    r"create\s+(?:a\s+)?(?:new\s+)?folder\s+(?:named\s+|called\s+)?"
    r"(?P<folder>[\w\\/.-]+)", re.IGNORECASE,
)
_DELETE_GOAL = re.compile(
    r"delete\s+(?:the\s+)?directory\s+(?:named\s+|called\s+)?"
    r"(?P<dir>[\w\\/.-]+)", re.IGNORECASE,
)


def _deterministic_plan(goal: str) -> list[dict[str, Any]] | None:
    """Plan simple, unambiguous goals directly — no LLM call, no junk steps."""
    m = _FILE_GOAL.search(goal)
    if m:
        path = f"{m.group('folder').rstrip('/\\')}/{m.group('name')}"
        content = m.group("content")
        return [{
            "id": "s1",
            "description": f"Create file {path} containing '{content}'",
            "tool": "create_file",
            "args": {"path": path, "content": content},
            "purpose": "fulfil the goal directly",
            "depends_on": [],
            "verify": {"type": "file_contains", "path": path, "expect": content},
        }]
    m = _DELETE_GOAL.search(goal)
    if m:
        d = m.group("dir").rstrip("/\\")
        return [{
            "id": "s1",
            "description": f"Delete directory {d} and everything in it",
            "tool": "delete_directory",
            "args": {"path": d},
            "purpose": "fulfil the goal directly",
            "depends_on": [],
            "verify": {"type": "none"},
        }]
    m = _FOLDER_GOAL.search(goal)
    if m:
        d = m.group("folder").rstrip("/\\")
        return [{
            "id": "s1",
            "description": f"Create folder {d}",
            "tool": "create_folder",
            "args": {"path": d},
            "purpose": "fulfil the goal directly",
            "depends_on": [],
            "verify": {"type": "none"},
        }]
    return None


async def plan_task_graph(
    goal: str, context: dict[str, Any] | None = None
) -> AgentTask:
    """Produce a validated AgentTask plan for a goal."""
    from dash_backend.llm.service import build_chat_messages, collect_streamed_response

    # Deterministic fast-path first: a goal that names exactly one
    # operation is planned by regex — the LLM only sees complex goals.
    direct = _deterministic_plan(goal)
    if direct:
        logger.info("deterministic plan used for goal: %.80s", goal)
        task = AgentTask(goal=goal)
        task.steps = _validate_steps(direct)
        return task

    context_str = ""
    if context:
        context_str = f"\nCONTEXT: {json.dumps(context, default=str)[:400]}"

    import os
    task_model = os.environ.get("DASH_TASK_MODEL") or None
    messages = build_chat_messages(
        system_prompt=PLANNER_GRAPH_PROMPT,
        user_message=f"GOAL: {goal}{context_str}\n\nReturn ONLY the JSON object with steps.",
    )
    try:
        raw = await collect_streamed_response(messages, model=task_model)
        steps = _parse_steps(raw)
    except Exception as exc:
        logger.warning("Graph planner LLM failed (%s) — falling back to linear plan", exc)
        steps = []

    if not steps:
        steps = await _linear_fallback(goal, context)

    task = AgentTask(goal=goal)
    task.steps = _validate_steps(steps)
    return task


def _parse_steps(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return []
    steps = data.get("steps") if isinstance(data, dict) else data
    return steps if isinstance(steps, list) else []


async def _linear_fallback(goal: str, context: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Degrade to the existing linear planner and map it onto a chain graph."""
    from dash_backend.autonomous.planner import plan_task

    plan = await plan_task(goal, context)
    steps: list[dict[str, Any]] = []
    prev_id: str | None = None
    for s in plan.steps:
        sid = f"s{s.index + 1}"
        steps.append({
            "id": sid,
            "description": s.description,
            "tool": s.tool,
            "args": s.args,
            "purpose": s.purpose,
            "depends_on": [prev_id] if prev_id else [],
            "verify": {"type": "none"},
        })
        prev_id = sid
    return steps


def _validate_steps(raw_steps: list[dict[str, Any]]) -> list[TaskStep]:
    """Deterministic validation — the security and sanity boundary."""
    # First pass: collect declared ids, coerce positional deps ("1","2") to ids.
    declared: list[str] = []
    for i, item in enumerate(raw_steps[:MAX_PLAN_STEPS]):
        sid = str(item.get("id") or f"s{i + 1}")
        declared.append(sid)
    id_set = set(declared)

    # Real registry inventory: names → (category, permission). Anything the
    # LLM invents that is not registered here becomes tool=None — the
    # orchestrator's runtime selection must pick a REAL tool, which is then
    # permission-checked like any other.
    inventory: dict[str, tuple[str, str]] = {}
    try:
        from dash_backend.tools.tool_manager import get_tool_manager
        manager = get_tool_manager()
        registry = getattr(manager, "_registry", None)
        if registry is not None:
            # get_all(), NOT all_tools() (decisions.md #91): the wrong
            # accessor raised AttributeError inside this broad except and
            # silently emptied the inventory — every planned tool was then
            # dropped to None at validation, forcing blind runtime LLM
            # selection. Failures here must never be silent.
            for name, tool in registry.get_all().items():
                inventory[name] = (
                    getattr(tool, "category", "") or "",
                    getattr(tool, "permission_level", None).value
                    if getattr(tool, "permission_level", None) else "auto",
                )
        if not inventory:
            logger.warning("tool registry inventory is EMPTY — planned tools "
                           "will be re-selected at runtime")
    except Exception:
        logger.exception("tool registry inventory unavailable — planned tools "
                         "will be re-selected at runtime")

    steps: list[TaskStep] = []
    for i, item in enumerate(raw_steps[:MAX_PLAN_STEPS]):
        sid = declared[i]
        tool = item.get("tool")
        tool = tool.strip() if isinstance(tool, str) and tool.strip() else None
        # Registry check: only REAL registered tools may be planned directly.
        if tool is not None and tool not in inventory:
            tool = None

        # Risk: RECOMPUTED from policy. LLM's declared risk is advisory only.
        risk_str = classify_risk(tool or "", inventory.get(tool, ("", ""))[0] if tool else None)
        try:
            risk = RiskLevel(risk_str)
        except ValueError:
            risk = RiskLevel.MODERATE

        # Dependencies: keep only earlier, known ids (kills cycles + forward refs)
        deps_raw = item.get("depends_on", []) or []
        deps: list[str] = []
        for d in deps_raw:
            d = str(d)
            if d in id_set and d != sid and declared.index(d) < i:
                deps.append(d)

        # Verify spec: type-checked against the verifier's supported set.
        # A file-existence intent without a concrete path (the model rarely
        # knows the final path at plan time) degrades honestly to a result-
        # derived check rather than a meaningless "file missing: ''".
        verify = item.get("verify")
        if not isinstance(verify, dict) or verify.get("type") not in VERIFY_TYPES:
            verify = {"type": "none"}
        if verify.get("type") == "file_exists" and not verify.get("path"):
            verify = {"type": "none"}

        steps.append(TaskStep(
            id=sid,
            index=i,
            description=str(item.get("description") or f"Step {i + 1}"),
            tool=tool,
            args=item.get("args") if isinstance(item.get("args"), dict) else {},
            purpose=str(item.get("purpose") or ""),
            risk=risk,
            depends_on=deps,
            verify=verify,
        ))
    _infer_dependencies(steps)
    return steps


# Lexical cue that a step VALIDATES/CHECKS a prior step's outcome rather than
# producing anything itself. Verified against the real live failure it
# prevents (decisions.md #91): the planner emitted s3="Verify that the text
# file was created successfully" with NO deps, so it ran in wave 1 and passed
# before the file existed.
_VERIFY_CUE = re.compile(
    r"\b(verify|check|confirm|validate|test that|ensure)\b", re.IGNORECASE
)


def _infer_dependencies(steps: list[TaskStep]) -> None:
    """Deterministic back-fill of missed dependencies.

    A verification/cue step that declared no dependencies is chained onto the
    nearest EARLIER producer step (the first non-verification step before it
    in plan order). The LLM forgot the edge; the graph must not lie about it.
    Steps with their own deps are trusted as-is.
    """
    for i, s in enumerate(steps):
        if s.depends_on or not _VERIFY_CUE.search(s.description):
            continue
        for j in range(i - 1, -1, -1):
            if not _VERIFY_CUE.search(steps[j].description):
                s.depends_on = [steps[j].id]
                break
