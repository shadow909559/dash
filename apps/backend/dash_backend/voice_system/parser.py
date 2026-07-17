"""Voice command parser and simple intent extraction.

This module provides a lightweight rule-based parser that can be used to map
short voice utterances to commands or intents. For richer natural language
understanding, integrate NLU providers or reuse the existing LLM pipeline to
parse commands.
"""
from __future__ import annotations

from typing import Dict, Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def parse_command(text: str) -> Dict[str, Any]:
    """Return a dict with keys: intent, args

    This simple parser recognizes a few built-in intents and otherwise returns
    the full text as a fallback for LLM processing.
    """
    t = (text or "").strip().lower()
    if not t:
        return {"intent": "empty", "args": {}}

    # Simple commands
    if t.startswith("open "):
        return {"intent": "open_url_or_app", "args": {"target": t[5:].strip()}}
    if t.startswith("search for ") or t.startswith("search "):
        q = t.split(" ", 1)[1] if " " in t else ""
        return {"intent": "search_web", "args": {"query": q}}
    if t in ("what's the time", "what is the time", "time"):
        return {"intent": "get_time", "args": {}}

    # Default: let LLM decide
    return {"intent": "llm_fallback", "args": {"text": text}}
