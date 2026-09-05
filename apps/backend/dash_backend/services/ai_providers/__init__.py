"""AI Providers package - abstraction layer for LLM providers.

Supports:
  - Ollama (local)
  - Gemini CLI
  - Qwen CLI
  - Future: OpenAI, Claude

Features:
  - Streaming responses
  - Cancellation via asyncio tasks
  - Configurable timeouts
  - Automatic fallback between providers
  - Provider health checks
"""

from __future__ import annotations

from .provider_manager import ProviderManager, get_provider_manager
from .base import AIProvider, ProviderConfig, ProviderHealth

__all__ = [
    "AIProvider",
    "ProviderConfig",
    "ProviderHealth",
    "ProviderManager",
    "get_provider_manager",
]
