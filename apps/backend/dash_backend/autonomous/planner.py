"""Task Planner — decomposes natural language goals into executable step plans.

The planner asks the LLM to break a complex goal into concrete steps,
each mapped to a tool the agent already has.  The agent loop then executes
each step through the normal observe→think→act cycle.

This is the bridge between "organize my downloads" and
"browse_folder → search_files → create_folder → (repeat)".
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

PLANNER_PROMPT = """\
You are a task planner for DASH, an autonomous AI agent on Windows.

Given a GOAL, break it into concrete, ordered steps.
Each step must be executable by calling ONE tool.

AVAILABLE TOOL CATEGORIES:
- filesystem: browse_folder, search_files, find_large_files, find_duplicate_files,
  create_folder, create_directory, delete_directory, list_special_folders,
  read_file, write_file, create_file, preview_file, list_recent_files
- system: system_info, disk_usage, list_running_processes
- desktop: list_running_processes, open_application, close_application,
  launch_application, take_screenshot, copy_text, read_clipboard
- network: list_wifi_profiles
- power: restart_system, sleep_system, hibernate_system
- browser: open_url, search_youtube, open_tab, close_tab

RESPONSE FORMAT (strict JSON array):
[
  {
    "description": "Human-readable step description",
    "tool": "tool_name or null if LLM should decide at runtime",
    "args": {"key": "value"} or {},
    "purpose": "Why this step is needed"
  }
]

RULES:
1. 3-8 steps. Be concrete, not vague.
2. Each step must be independently executable.
3. Use "null" for tool when the step requires judgment (e.g., "review results").
4. Order matters — later steps may depend on earlier ones.
5. If the goal is simple (one tool call), return a single step.
6. Return ONLY the JSON array. No explanation.
"""


@dataclass
class PlanStep:
    """One step in a task plan."""
    index: int
    description: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    purpose: str = ""
    status: str = "pending"  # pending | active | done | failed | skipped
    result_summary: str | None = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "description": self.description,
            "tool": self.tool,
            "status": self.status,
            "purpose": self.purpose,
            "result_summary": self.result_summary,
        }


@dataclass
class TaskPlan:
    """A decomposed plan for a complex goal."""
    goal_description: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @property
    def current_step(self) -> PlanStep | None:
        for s in self.steps:
            if s.status == "pending":
                return s
        return None

    @property
    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status in ("done", "skipped"))

    @property
    def failed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "failed")

    @property
    def is_complete(self) -> bool:
        return all(s.status in ("done", "skipped", "failed") for s in self.steps)

    @property
    def progress_pct(self) -> int:
        if not self.steps:
            return 0
        return int((self.completed_count / len(self.steps)) * 100)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal_description,
            "steps": [s.to_dict() for s in self.steps],
            "progress": f"{self.completed_count}/{len(self.steps)}",
            "progress_pct": self.progress_pct,
        }


def is_complex_goal(description: str) -> bool:
    """Heuristic: should this goal be decomposed into a plan?

    Simple goals (single tool calls) skip planning.
    Complex goals (multi-step, multi-tool) benefit from decomposition.
    """
    desc = description.lower().strip()

    # Multi-step indicators (check BEFORE word count — these signal
    # complexity even in short descriptions like 'set up a backup')
    complex_signals = [
        "and then", "after that", "first", "organize", "clean up",
        "set up", "configure", "find all", "search for all",
        "create a", "make a backup", "review", "audit",
        "compare", "analyze", "summarize", "report",
        "optimize", "improve", "fix all", "check everything",
    ]
    if any(signal in desc for signal in complex_signals):
        return True

    # Short descriptions without complex signals are likely simple commands
    if len(desc.split()) < 6:
        return False
    if any(signal in desc for signal in complex_signals):
        return True

    # Multiple tool-category words
    tool_words = ["file", "folder", "process", "disk", "memory", "clipboard",
                   "browser", "wifi", "screenshot", "application"]
    word_count = sum(1 for w in tool_words if w in desc)
    if word_count >= 2:
        return True

    return False


async def plan_task(description: str, context: dict[str, Any] | None = None) -> TaskPlan:
    """Use the LLM to decompose a goal into a concrete step plan.

    Returns a TaskPlan with ordered steps, each mapped to a tool.
    """
    from dash_backend.llm.service import build_chat_messages, collect_streamed_response

    context_str = ""
    if context:
        context_str = f"\nCONTEXT: {json.dumps(context)[:500]}"

    messages = build_chat_messages(
        system_prompt=PLANNER_PROMPT,
        user_message=f"GOAL: {description}{context_str}\n\nBreak this into concrete steps. Return ONLY a JSON array.",
    )

    try:
        raw = await collect_streamed_response(messages)
        plan = _parse_plan(raw, description)
        logger.info(
            "Task planner: %d steps for '%s'",
            len(plan.steps), description[:60],
        )
        return plan
    except Exception as exc:
        logger.warning("Task planner failed, creating single-step fallback: %s", exc)
        return TaskPlan(
            goal_description=description,
            steps=[PlanStep(index=0, description=description, tool=None)],
        )


def _parse_plan(raw: str, description: str) -> TaskPlan:
    """Parse LLM output into a TaskPlan."""
    text = raw.strip()

    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            data = json.loads(text[start:end + 1])
        else:
            logger.warning("Could not parse planner output as JSON")
            return TaskPlan(
                goal_description=description,
                steps=[PlanStep(index=0, description=description, tool=None)],
            )

    if not isinstance(data, list):
        data = [data]

    steps = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            steps.append(PlanStep(
                index=i,
                description=item.get("description", f"Step {i+1}"),
                tool=item.get("tool"),
                args=item.get("args", {}),
                purpose=item.get("purpose", ""),
            ))

    if not steps:
        steps = [PlanStep(index=0, description=description, tool=None)]

    return TaskPlan(goal_description=description, steps=steps)
