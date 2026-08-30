"""Ollama provider - local LLM inference via Ollama API."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator

import httpx

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderCapability,
    ProviderConfig,
    ProviderHealth,
)

logger = get_logger(__name__)

_DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(AIProvider):
    """Provider for local Ollama inference."""

    def __init__(
        self,
        model: str = "llama3.2:3b",
        base_url: str = _DEFAULT_BASE_URL,
        timeout: int = 120,
    ) -> None:
        self._config = ProviderConfig(
            name="ollama",
            model=model,
            base_url=base_url,
            timeout_seconds=timeout,
            capabilities={
                ProviderCapability.TEXT_COMPLETION,
                ProviderCapability.CHAT,
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
            },
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        self._cancelled = False

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def config(self) -> ProviderConfig:
        return self._config

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._cancelled = False
        payload = {
            "model": self._config.model,
            "messages": self._build_messages(request),
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.stop_sequences:
            payload["options"]["stop"] = request.stop_sequences

        response = await self._client.post(
            f"{self._config.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        return CompletionResponse(
            content=data.get("message", {}).get("content", ""),
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    async def complete_streaming(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._cancelled = False
        payload = {
            "model": self._config.model,
            "messages": self._build_messages(request),
            "stream": True,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }

        async with self._client.stream(
            "POST", f"{self._config.base_url}/api/chat", json=payload
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if self._cancelled:
                    break
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done", False):
                        break
                except json.JSONDecodeError:
                    continue

    async def check_health(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            response = await self._client.get(
                f"{self._config.base_url}/api/tags", timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            model_loaded = self._config.model in models
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(
                healthy=True,
                latency_ms=round(latency, 1),
                model_loaded=model_loaded,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(
                healthy=False,
                latency_ms=round(latency, 1),
                error=str(exc),
            )

    async def cancel(self) -> None:
        self._cancelled = True

    @staticmethod
    def _build_messages(request: CompletionRequest) -> list[dict[str, str]]:
        messages = list(request.messages)
        if request.system_prompt:
            messages.insert(0, {"role": "system", "content": request.system_prompt})
        return messages
