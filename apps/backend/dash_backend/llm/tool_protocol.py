from __future__ import annotations

from enum import Enum

from dash_backend.config import get_settings


class ToolProtocol(str, Enum):
    CUSTOM_JSON = "CUSTOM_JSON"
    OPENAI_NATIVE = "OPENAI_NATIVE"


def get_tool_protocol() -> ToolProtocol:
    """Return the tool-calling protocol to use for the current request.

    This is the single decision point for tool protocol selection.
    """

    settings = get_settings()
    provider = (settings.ai_provider or "").lower()

    if provider == "ollama":
        return ToolProtocol.CUSTOM_JSON

    # OpenAI/LiteLLM-style providers expect native tool call sequencing.
    return ToolProtocol.OPENAI_NATIVE


