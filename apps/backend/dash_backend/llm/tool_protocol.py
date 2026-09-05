from __future__ import annotations

from enum import Enum

from dash_backend.config import get_settings


class ToolProtocol(str, Enum):
    CUSTOM_JSON = "CUSTOM_JSON"
    OPENAI_NATIVE = "OPENAI_NATIVE"


def get_tool_protocol() -> ToolProtocol:
    """Return the tool-calling protocol to use for the current request.

    This is the single decision point for tool protocol selection.
    Both providers now use native tool calling: Ollama via /api/chat
    `tools`, OpenAI-compatible via /chat/completions `tools`.
    CUSTOM_JSON remains available as an explicit legacy fallback via
    DASH_TOOL_PROTOCOL=custom_json if ever needed.
    """
    settings = get_settings()
    override = getattr(settings, "tool_protocol", "").lower()
    if override == "custom_json":
        return ToolProtocol.CUSTOM_JSON

    return ToolProtocol.OPENAI_NATIVE


