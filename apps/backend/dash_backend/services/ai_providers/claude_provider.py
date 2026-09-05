"""Anthropic Claude provider — supports Claude 3.5 Sonnet, Opus, Haiku, etc."""

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


class ClaudeProvider(AIProvider):
    """Provider for Anthropic Claude models."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com/v1",
        timeout: int = 120,
    ) -> None:
        self._config = ProviderConfig(
            name="claude",
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
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        self._cancelled = False

    @property
    def name(self) -> str:
        return "claude"

    @property
    def config(self) -> ProviderConfig:
        return self._config

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._cancelled = False
        messages = [{"role": m["role"], "content": m["content"]} for m in request.messages]

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.system_prompt:
            body["system"] = request.system_prompt

        try:
            resp = await self._client.post(
                f"{self._config.base_url}/messages",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            return CompletionResponse(
                content=content,
                finish_reason=data.get("stop_reason", "stop"),
                usage=data.get("usage"),
            )
        except Exception as exc:
            logger.exception("Claude completion failed")
            raise RuntimeError(f"Claude error: {exc}") from exc

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._cancelled = False
        messages = [{"role": m["role"], "content": m["content"]} for m in request.messages]

        body: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": True,
        }
        if request.system_prompt:
            body["system"] = request.system_prompt

        try:
            async with self._client.stream(
                "POST",
                f"{self._config.base_url}/messages",
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if self._cancelled:
                        break
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        event = json.loads(payload)
                        if event.get("type") == "content_block_delta":
                            text = event.get("delta", {}).get("text", "")
                            if text:
                                yield text
                        elif event.get("type") == "message_stop":
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            logger.exception("Claude streaming failed")
            raise RuntimeError(f"Claude streaming error: {exc}") from exc

    async def health(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            # Anthropic doesn't have a models endpoint, so just check auth
            resp = await self._client.get(f"{self._config.base_url}/models")
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(healthy=True, latency_ms=latency, model_loaded=True)
        except httpx.HTTPStatusError as exc:
            latency = (time.monotonic() - start) * 1000
            if exc.response.status_code == 401:
                return ProviderHealth(healthy=False, latency_ms=latency, error="Invalid API key")
            # 404 on models endpoint is fine — key is valid
            return ProviderHealth(healthy=True, latency_ms=latency, model_loaded=True)
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(healthy=False, latency_ms=latency, error=str(exc))

    async def cancel(self) -> None:
        self._cancelled = True
