"""OpenAI-compatible AI provider — works with OpenAI, ChatGPT, Codex, Cursor, Groq, Together, etc."""

from __future__ import annotations

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


class OpenAIProvider(AIProvider):
    """Provider for OpenAI and OpenAI-compatible APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout: int = 120,
    ) -> None:
        self._config = ProviderConfig(
            name="openai",
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout_seconds=timeout,
            capabilities={
                ProviderCapability.TEXT_COMPLETION,
                ProviderCapability.CHAT,
                ProviderCapability.STREAMING,
                ProviderCapability.TOOL_CALLING,
                ProviderCapability.VISION,
            },
        )
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        self._cancelled = False

    @property
    def name(self) -> str:
        return "openai"

    @property
    def config(self) -> ProviderConfig:
        return self._config

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._cancelled = False
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            body["tools"] = request.tools
        if request.stop_sequences:
            body["stop"] = request.stop_sequences

        try:
            resp = await self._client.post(
                f"{self._config.base_url}/chat/completions",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            return CompletionResponse(
                content=choice["message"].get("content", ""),
                finish_reason=choice.get("finish_reason", "stop"),
                usage=data.get("usage"),
            )
        except Exception as exc:
            logger.exception("OpenAI completion failed")
            raise RuntimeError(f"OpenAI error: {exc}") from exc

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._cancelled = False
        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.extend(request.messages)

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }
        if request.tools:
            body["tools"] = request.tools

        try:
            async with self._client.stream(
                "POST",
                f"{self._config.base_url}/chat/completions",
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if self._cancelled:
                        break
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(payload)
                        delta = chunk["choices"][0].get("delta", {})
                        text = delta.get("content")
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as exc:
            logger.exception("OpenAI streaming failed")
            raise RuntimeError(f"OpenAI streaming error: {exc}") from exc

    async def health(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            resp = await self._client.get(f"{self._config.base_url}/models")
            resp.raise_for_status()
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(
                healthy=True,
                latency_ms=latency,
                model_loaded=True,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(
                healthy=False,
                latency_ms=latency,
                error=str(exc),
            )

    async def cancel(self) -> None:
        self._cancelled = True
