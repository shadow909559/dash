"""Google Gemini provider — supports Gemini 1.5 Flash, Pro, etc."""

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


class GeminiProvider(AIProvider):
    """Provider for Google Gemini models."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-1.5-flash",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout: int = 120,
    ) -> None:
        self._config = ProviderConfig(
            name="gemini",
            model=model,
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout_seconds=timeout,
            capabilities={
                ProviderCapability.TEXT_COMPLETION,
                ProviderCapability.CHAT,
                ProviderCapability.STREAMING,
                ProviderCapability.VISION,
            },
        )
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
        self._cancelled = False

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def config(self) -> ProviderConfig:
        return self._config

    def _build_contents(self, request: CompletionRequest) -> list[dict]:
        contents = []
        if request.system_prompt:
            contents.append({
                "role": "user",
                "parts": [{"text": f"System: {request.system_prompt}"}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood."}],
            })
        for m in request.messages:
            role = "user" if m["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        return contents

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._cancelled = False
        url = f"{self._config.base_url}/models/{self._config.model}:generateContent?key={self._config.api_key}"
        body = {
            "contents": self._build_contents(request),
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        try:
            resp = await self._client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return CompletionResponse(content=text, finish_reason="stop")
        except Exception as exc:
            logger.exception("Gemini completion failed")
            raise RuntimeError(f"Gemini error: {exc}") from exc

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._cancelled = False
        url = f"{self._config.base_url}/models/{self._config.model}:streamGenerateContent?key={self._config.api_key}&alt=sse"
        body = {
            "contents": self._build_contents(request),
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        try:
            async with self._client.stream("POST", url, json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if self._cancelled:
                        break
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    try:
                        data = json.loads(payload)
                        text = data["candidates"][0]["content"]["parts"][0].get("text", "")
                        if text:
                            yield text
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except Exception as exc:
            logger.exception("Gemini streaming failed")
            raise RuntimeError(f"Gemini streaming error: {exc}") from exc

    async def health(self) -> ProviderHealth:
        start = time.monotonic()
        try:
            url = f"{self._config.base_url}/models?key={self._config.api_key}"
            resp = await self._client.get(url)
            resp.raise_for_status()
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(healthy=True, latency_ms=latency, model_loaded=True)
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(healthy=False, latency_ms=latency, error=str(exc))

    async def cancel(self) -> None:
        self._cancelled = True
