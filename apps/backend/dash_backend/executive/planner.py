from __future__ import annotations

import json
import logging
from typing import List, Dict, Any

from dash_backend.llm.service import collect_streamed_response, build_chat_messages
from dash_backend.config import get_settings

logger = logging.getLogger(__name__)


class Planner:
    """Planner abstraction that uses the configured LLM provider to decompose
    high-level goals into structured subtasks.

    The Planner is provider-agnostic and relies on dash_backend.llm.service
    to call the configured AI provider (OpenAI, Ollama, etc.).

    The default implementation asks the model to return a JSON array of
    tasks with fields: name, description, est_minutes (optional), tools (optional).
    If the provider is not configured or the response cannot be parsed, the
    planner falls back to a simple sentence-splitting heuristic.
    """

    @staticmethod
    async def decompose(goal_name: str, goal_description: str | None = None, max_tasks: int = 10) -> List[Dict[str, Any]]:
        prompt = (
            "You are a task planner. Break the user's goal into a list of up to "
            f"{max_tasks} clear, actionable subtasks. Return the result as JSON array of objects with keys:\n"
            "- name (short task name)\n"
            "- description (one-line description)\n"
            "- est_minutes (optional, estimated minutes)\n"
            "- tools (optional, list of tools/skills required)\n"
            "Respond with JSON only. Do not include any additional explanation.\n\n"
        )

        user_message = f"Goal: {goal_name}\n\nDescription: {goal_description or ''}\n\nProduce the JSON array of subtasks."

        messages = build_chat_messages(system_prompt=prompt, user_message=user_message)

        try:
            text = await collect_streamed_response(messages)
            # Expecting JSON array
            text = text.strip()
            # Some models may wrap JSON in code fences; try to extract
            if text.startswith("```"):
                # strip code fences
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1].strip()
            tasks = json.loads(text)
            if isinstance(tasks, list):
                # normalize items
                normalized = []
                for t in tasks[:max_tasks]:
                    if not isinstance(t, dict):
                        continue
                    normalized.append({
                        "name": str(t.get("name") or t.get("title") or "Unnamed Task")[:255],
                        "description": str(t.get("description") or "")[:1000],
                        "est_minutes": int(t.get("est_minutes")) if t.get("est_minutes") else None,
                        "tools": t.get("tools") or [],
                    })
                if normalized:
                    return normalized
        except Exception as exc:
            logger.warning("Planner LLM decomposition failed: %s", exc)

        # Fallback heuristic: split description into sentences/lines
        if goal_description:
            parts = [p.strip() for p in goal_description.replace("!", ".").replace("?", ".").split('.') if p.strip()]
            return [{"name": (p[:255] if len(p) <= 255 else p[:255]), "description": p, "est_minutes": None, "tools": []} for p in parts[:max_tasks]]
        return [{"name": goal_name, "description": goal_description or goal_name, "est_minutes": None, "tools": []}]
