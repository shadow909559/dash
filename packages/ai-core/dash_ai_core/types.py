"""AI provider configuration types (scaffold)."""

from enum import Enum


class AIProvider(str, Enum):
    """Supported AI provider identifiers."""

    OPENAI = "openai"
    OLLAMA = "ollama"
