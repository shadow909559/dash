"""Direct cloud AI call — bypasses config system for reliable fallback."""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

import httpx

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Cloud provider configs (fastest first)
_CLOUD_PROVIDERS = [
    {
        "name": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": "",  # filled at runtime
        "model": "qwen/qwen3.6-27b",
    },
    {
        "name": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key": "",
        "model": "gemini-3.6-flash",
    },
]


def _get_cloud_providers() -> list[dict]:
    """Get cloud providers with API keys from config."""
    from dash_backend.config import get_settings
    settings = get_settings()

    providers = []
    # Groq first (fastest)
    if settings.groq_api_key:
        providers.append({
            "name": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": settings.groq_api_key,
            "model": settings.groq_model or "qwen/qwen3.6-27b",
        })
    # Gemini second
    if settings.gemini_api_key:
        providers.append({
            "name": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "api_key": settings.gemini_api_key,
            "model": settings.gemini_model or "gemini-3.6-flash",
        })
    # Generic OpenAI-compatible third
    if settings.openai_api_key and settings.openai_base_url:
        providers.append({
            "name": "openai",
            "base_url": settings.openai_base_url.rstrip("/"),
            "api_key": settings.openai_api_key,
            "model": settings.openai_model or "gpt-4o-mini",
        })
    return providers


async def cloud_chat(messages: list[dict], timeout: float = 30.0) -> str:
    """Call cloud AI providers in order, return first successful response."""
    providers = _get_cloud_providers()

    for provider in providers:
        try:
            url = f"{provider['base_url']}/chat/completions"
            headers = {
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": provider["model"],
                "messages": messages,
                "stream": False,
                "max_tokens": 2048,
            }

            logger.info("Cloud fallback: trying %s with model %s", provider["name"], provider["model"])
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    # Strip <think>...</think> tags from thinking models
                    import re
                    content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                    if content:
                        logger.info("Cloud fallback: %s responded (%d chars)", provider["name"], len(content))
                        return content
                else:
                    logger.warning("Cloud fallback: %s returned %d: %s", provider["name"], resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.warning("Cloud fallback: %s failed: %s", provider["name"], exc)
            continue

    return ""


async def cloud_chat_stream(messages: list[dict], timeout: float = 30.0) -> AsyncIterator[str]:
    """Stream from cloud AI providers. Falls back to non-streaming if needed."""
    providers = _get_cloud_providers()

    for provider in providers:
        try:
            url = f"{provider['base_url']}/chat/completions"
            headers = {
                "Authorization": f"Bearer {provider['api_key']}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": provider["model"],
                "messages": messages,
                "stream": True,
            }

            logger.info("Cloud stream: trying %s", provider["name"])
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        logger.warning("Cloud stream: %s returned %d", provider["name"], resp.status_code)
                        continue
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            import json
                            try:
                                chunk = json.loads(line[6:])
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                    return  # success
        except Exception as exc:
            logger.warning("Cloud stream: %s failed: %s", provider["name"], exc)
            continue

    # All providers failed — try non-streaming fallback
    result = await cloud_chat(messages, timeout)
    if result:
        yield result
