"""Base AI provider interface and configuration models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator


class ProviderCapability(Enum):
    """Capabilities a provider may support."""
    TEXT_COMPLETION = "text_completion"
    CHAT = "chat"
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    EMBEDDINGS = "embeddings"


@dataclass
class ProviderConfig:
    """Configuration for an AI provider."""
    name: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    timeout_seconds: int = 60
    max_retries: int = 3
    rate_limit_per_minute: int = 60
    enabled: bool = True
    capabilities: set[ProviderCapability] = field(default_factory=lambda: {
        ProviderCapability.TEXT_COMPLETION,
        ProviderCapability.CHAT,
    })
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderHealth:
    """Health status of a provider."""
    healthy: bool
    latency_ms: float = 0.0
    last_check: datetime | None = None
    error: str | None = None
    model_loaded: bool = False


@dataclass
class CompletionRequest:
    """Request for a text completion / chat interaction."""
    messages: list[dict[str, str]]
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    stop_sequences: list[str] | None = None


@dataclass
class CompletionResponse:
    """Response from a completion request."""
    content: str
    finish_reason: str = "stop"
    usage: dict[str, int] | None = None


class AIProvider(ABC):
    """Abstract base class for all AI providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'ollama', 'gemini-cli', 'qwen-cli')."""
        ...

    @property
    @abstractmethod
    def config(self) -> ProviderConfig:
        """Provider configuration."""
        ...

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        ...

    @abstractmethod
    def complete_streaming(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Streaming completion - yields content tokens."""
        ...

    @abstractmethod
    async def check_health(self) -> ProviderHealth:
        """Check if the provider is healthy and responsive."""
        ...

    async def cancel(self) -> None:
        """Cancel any in-flight requests."""
        pass
