"""LLM service that calls OpenAI-compatible APIs or Ollama with streaming.

Integrates conversation history, memory context, and conversation
summaries to build rich prompts for the AI model.

This module now also supports tool-call detection:
- Collect a full streamed response
- Detect whether the response is a JSON tool_call
- Validate schema and parse into a structured result
- Never crash on malformed JSON (falls back to assistant text)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class AssistantResponse:
    text: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


ToolOrAssistant = AssistantResponse | ToolCall


async def _detect_ollama_model() -> str | None:
    """Query Ollama /api/tags and return the first available llama-compatible model."""
    settings = get_settings()
    base_url = settings.ollama_base_url.rstrip("/")
    tags_url = f"{base_url}/api/tags"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(tags_url)
            if response.status_code != 200:
                logger.warning("Ollama /api/tags returned %s", response.status_code)
                return None

            data = response.json()
            models = data.get("models", [])
            if not models:
                logger.warning("No models found in Ollama")
                return None

            # Prefer llama-compatible models
            preferred_keywords = ["llama", "mistral", "qwen", "mixtral", "gemma"]
            for model_entry in models:
                name = model_entry.get("name", "")
                name_lower = name.lower()
                for keyword in preferred_keywords:
                    if keyword in name_lower:
                        logger.info("Auto-selected Ollama model: %s", name)
                        return name

            # Fall back to first available model
            first_model = models[0].get("name", "")
            logger.info("Auto-selected Ollama model (fallback): %s", first_model)
            return first_model

    except httpx.RequestError as exc:
        logger.warning("Could not reach Ollama at %s: %s", base_url, exc)
        return None
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.warning("Failed to parse Ollama /api/tags response: %s", exc)
        return None


async def stream_chat_response(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream a chat completion from the configured AI provider.

    Supports OpenAI-compatible APIs and Ollama.
    Yields content tokens as they arrive.
    """
    settings = get_settings()

    provider = settings.ai_provider.lower()
    logger.info("Using AI provider: %s", provider)

    if provider == "ollama":
        async for token in _stream_ollama(messages, model):
            yield token
    else:
        async for token in _stream_openai(messages, model):
            yield token


async def collect_streamed_response(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> str:
    """Collect the full assistant output from the existing streaming API."""
    parts: list[str] = []
    async for token in stream_chat_response(messages, model=model):
        parts.append(token)
    return "".join(parts)


def parse_tool_call_from_text(text: str) -> ToolOrAssistant:
    """Parse a model output into either ToolCall or AssistantResponse.

    Expected tool-call JSON:
    {
      "type": "tool_call",
      "tool": "tool_name",
      "arguments": { ... }
    }

    Rules:
    - If JSON parsing fails, treat output as assistant text.
    - Validate required fields.
    - Reject malformed tool calls (return AssistantResponse).
    - Never crash.
    """
    raw = (text or "").strip()
    if not raw:
        return AssistantResponse(text="")

    # Fast-path: only attempt JSON parse if it looks like JSON.
    # This is intentionally permissive to avoid false negatives.
    if not (raw.startswith("{") and raw.endswith("}")):
        return AssistantResponse(text=text)

    try:
        payload = json.loads(raw)
    except Exception:
        return AssistantResponse(text=text)

    if not isinstance(payload, dict):
        return AssistantResponse(text=text)

    # Validate schema
    p_type = payload.get("type")
    p_tool = payload.get("tool")
    p_args = payload.get("arguments")

    if p_type != "tool_call":
        return AssistantResponse(text=text)

    if not isinstance(p_tool, str) or not p_tool.strip():
        return AssistantResponse(text=text)

    if not isinstance(p_args, dict):
        return AssistantResponse(text=text)

    # Ensure arguments values are JSON-compatible primitives/objects.
    # We don't enforce deeper schemas here; tool execution will validate.
    return ToolCall(name=p_tool.strip(), arguments=p_args)


async def chat_completion_with_tool_parsing(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> ToolOrAssistant:
    """Collect the assistant response, then parse as tool_call or plain text."""
    full_text = await collect_streamed_response(messages, model=model)
    return parse_tool_call_from_text(full_text)


async def _stream_openai(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream from an OpenAI-compatible API."""
    settings = get_settings()

    api_key = settings.openai_api_key
    if not api_key:
        logger.warning("No OPENAI_API_KEY configured, returning fallback response")
        yield "I'm sorry, but no AI provider is configured. Please set the DASH_OPENAI_API_KEY or DASH_OLLAMA_BASE_URL environment variable."
        return

    base_url = settings.openai_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    model_name = model or settings.ai_model or settings.openai_model
    logger.info("Sending prompt to OpenAI model: %s", model_name)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(
                        "OpenAI API error: %s %s",
                        response.status_code,
                        error_text,
                    )
                    yield f"*Error: AI provider returned status {response.status_code}*"
                    return

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        return

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content

    except httpx.TimeoutException:
        logger.error("OpenAI API request timed out")
        yield "*Error: AI provider request timed out*"
    except httpx.RequestError as exc:
        logger.error("OpenAI API request failed: %s", exc)
        yield f"*Error: Could not reach AI provider: {exc}*"


async def _stream_ollama(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream from an Ollama instance with auto-detection of available models."""
    settings = get_settings()

    base_url = settings.ollama_base_url.rstrip("/")
    url = f"{base_url}/api/chat"

    # Auto-detect model if not explicitly provided
    if model:
        model_name = model
    elif settings.ai_model:
        model_name = settings.ai_model
    else:
        detected = await _detect_ollama_model()
        if detected:
            model_name = detected
        else:
            model_name = settings.ollama_model
            logger.warning("Ollama model detection failed, using default: %s", model_name)

    logger.info("Sending prompt to Ollama model: %s", model_name)

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": True,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(
                        "Ollama API error: %s %s",
                        response.status_code,
                        error_text,
                    )
                    yield f"*Error: Ollama returned status {response.status_code}: {error_text.decode(errors='replace')[:200]}*"
                    return

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content

    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        yield "*Error: AI provider request timed out*"
    except httpx.RequestError as exc:
        logger.error("Ollama request failed: %s", exc)
        yield f"*Error: Could not reach Ollama: {exc}*"


def build_chat_messages(
    system_prompt: str | None = None,
    history: list[dict[str, str]] | None = None,
    user_message: str = "",
    memory_context: str | None = None,
    conversation_summary: str | None = None,
) -> list[dict[str, str]]:
    """Build the messages array for an LLM chat completion request.

    Incorporates memory context and conversation summaries into
    the system prompt for richer context-aware responses.

    Args:
        system_prompt: Base system prompt.
        history: Previous conversation messages.
        user_message: Current user message.
        memory_context: Injected memory context string.
        conversation_summary: Injected conversation summary.

    Returns:
        List of message dicts for the LLM API.
    """
    messages: list[dict[str, str]] = []

    # Build enriched system prompt
    system_parts: list[str] = []

    if system_prompt:
        system_parts.append(system_prompt)

    if memory_context:
        system_parts.append("\n[USER MEMORY CONTEXT]")
        system_parts.append(memory_context)
        system_parts.append("[/USER MEMORY CONTEXT]\n")

    if conversation_summary:
        system_parts.append("\n[CONVERSATION SUMMARY]")
        system_parts.append(conversation_summary)
        system_parts.append("[/CONVERSATION SUMMARY]\n")

    if system_parts:
        messages.append({"role": "system", "content": "\n".join(system_parts)})

    if history:
        messages.extend(history)

    if user_message:
        messages.append({"role": "user", "content": user_message})

    return messages

