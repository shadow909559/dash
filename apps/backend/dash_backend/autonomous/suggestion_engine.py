"""Suggestion Engine - Proactive automation and workflow suggestions."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from dash_backend.llm.service import collect_streamed_response, build_chat_messages

logger = logging.getLogger(__name__)


class SuggestionEngine:
    def __init__(self):
        self._suggestions: List[Dict[str, Any]] = []

    async def generate(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            ctx = "\n".join(f"{k}: {v}" for k, v in context.items())
            messages = build_chat_messages(
                system_prompt="Suggest automations. Return JSON array of suggestions with 'title', 'description', 'action', 'confidence'.",
                user_message=f"Suggest helpful automations:\n{ctx}",
            )
            text = await collect_streamed_response(messages)
            try:
                items = json.loads(text)
                if isinstance(items, list):
                    self._suggestions.extend(items)
                    return items
            except json.JSONDecodeError:
                pass
        except Exception as exc:
            logger.warning("Suggestion generation failed: %s", exc)
        return []

    def get(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._suggestions[:limit]

    def dismiss(self, index: int) -> bool:
        if 0 <= index < len(self._suggestions):
            self._suggestions.pop(index)
            return True
        return False

    def clear(self) -> None:
        self._suggestions.clear()


_suggestion_engine: Optional[SuggestionEngine] = None


def get_suggestion_engine() -> SuggestionEngine:
    global _suggestion_engine
    if _suggestion_engine is None:
        _suggestion_engine = SuggestionEngine()
    return _suggestion_engine
