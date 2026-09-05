"""Daily Planner - Autonomous daily planning and task organization."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from dash_backend.llm.service import collect_streamed_response, build_chat_messages

logger = logging.getLogger(__name__)


@dataclass
class DailyPlan:
    date: str = ""
    summary: str = ""
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    priorities: List[str] = field(default_factory=list)
    goals: List[str] = field(default_factory=list)
    notes: str = ""


class DailyPlanner:
    def __init__(self):
        self._plans: Dict[str, DailyPlan] = {}

    async def create_plan(self, context: Optional[str] = None) -> DailyPlan:
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            messages = build_chat_messages(
                system_prompt="You are a daily planner. Create a structured plan. Return JSON with 'summary', 'tasks' (list with 'name', 'priority', 'estimated_minutes'), 'priorities', 'goals', 'notes'.",
                user_message=f"Create a daily plan for {today}. Context: {context or 'General productivity'}",
            )
            text = await collect_streamed_response(messages)
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {"summary": text[:200], "tasks": [], "priorities": [], "goals": []}
            plan = DailyPlan(
                date=today, summary=data.get("summary", ""),
                tasks=data.get("tasks", []), priorities=data.get("priorities", []),
                goals=data.get("goals", []), notes=data.get("notes", ""),
            )
        except Exception:
            plan = DailyPlan(date=today, summary="Could not generate plan")
        self._plans[today] = plan
        return plan

    def get_plan(self, date: Optional[str] = None) -> Optional[DailyPlan]:
        return self._plans.get(date or datetime.now().strftime("%Y-%m-%d"))

    def list_plans(self) -> List[str]:
        return sorted(self._plans.keys(), reverse=True)


_daily_planner: Optional[DailyPlanner] = None


def get_daily_planner() -> DailyPlanner:
    global _daily_planner
    if _daily_planner is None:
        _daily_planner = DailyPlanner()
    return _daily_planner
