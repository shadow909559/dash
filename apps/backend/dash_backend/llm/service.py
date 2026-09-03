"""LLM service that calls OpenAI-compatible APIs or Ollama with streaming.

Integrates conversation history, memory context, and conversation
summaries to build rich prompts for the AI model.

This module now also supports tool-call detection:
- Collect a full streamed response
- Detect whether the response is a JSON tool_call
- Validate schema and parse into a structured result
- Never crash on malformed JSON (falls back to assistant text)

Features:
- Streaming responses with timeout
- Retry logic with exponential backoff
- Health check for AI providers
- Automatic reconnect on connection failures
- Context window handling and history truncation
- Token estimation
- System prompt injection
- Input sanitization for prompt injection prevention
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import httpx

from dash_backend.config import get_settings
from dash_backend.llm.openai_message_validator import validate_openai_message_history
from dash_backend.logging_config import get_logger
from dash_backend.security.input_sanitizer import sanitize_for_llm, sanitize_memory_context


logger = get_logger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0
RETRY_BACKOFF_MULTIPLIER = 2.0


@dataclass(frozen=True)
class AssistantResponse:
    text: str


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


ToolOrAssistant = AssistantResponse | ToolCall


async def check_provider_health() -> dict[str, Any]:
    """Check the health of the configured AI provider.
    
    Returns a dict with:
    - healthy: bool
    - provider: str
    - configured_model: str | None
    - model_available: bool
    - installed_models: list[str]
    - error: str | None
    - latency_ms: float | None
    """
    settings = get_settings()
    provider = settings.ai_provider.lower()
    
    result = {
        "healthy": False,
        "provider": provider,
        "configured_model": None,
        "model_available": False,
        "installed_models": [],
        "error": None,
        "latency_ms": None,
    }
    
    try:
        if provider == "ollama":
            # Check Ollama health via /api/tags
            base_url = settings.ollama_base_url.rstrip("/")
            tags_url = f"{base_url}/api/tags"
            
            start_time = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(tags_url)
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    installed_models = [m.get("name", "") for m in models if m.get("name")]
                    
                    result["healthy"] = True
                    result["installed_models"] = installed_models
                    result["latency_ms"] = latency_ms
                    
                    # Determine configured model with proper priority
                    configured_model = None
                    if settings.ai_model:
                        configured_model = settings.ai_model
                    elif settings.ollama_model:
                        configured_model = settings.ollama_model
                    
                    result["configured_model"] = configured_model
                    # Check if configured model is available (with or without :latest suffix)
                    if configured_model:
                        result["model_available"] = any(
                            configured_model == m or
                            configured_model == m.replace(":latest", "") or
                            f"{configured_model}:latest" == m
                            for m in installed_models
                        )
                    else:
                        result["model_available"] = False
                else:
                    result["error"] = f"Ollama returned status {response.status_code}"
        else:
            # Check OpenAI-compatible provider health
            api_key = settings.openai_api_key
            if not api_key:
                result["error"] = "No OPENAI_API_KEY configured"
                return result
            
            base_url = settings.openai_base_url.rstrip("/")
            # Use a minimal request to check connectivity
            models_url = f"{base_url}/models"
            
            start_time = asyncio.get_event_loop().time()
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                
                if response.status_code == 200:
                    result["healthy"] = True
                    configured_model = settings.ai_model or settings.openai_model
                    result["configured_model"] = configured_model
                    result["model_available"] = True
                    result["latency_ms"] = latency_ms
                else:
                    result["error"] = f"Provider returned status {response.status_code}"
    except asyncio.TimeoutError:
        result["error"] = "Health check timed out"
    except httpx.RequestError as exc:
        result["error"] = f"Could not reach provider: {exc}"
    except Exception as exc:
        result["error"] = f"Health check failed: {exc}"
    
    return result


async def _retry_with_backoff(
    func,
    *args,
    max_retries: int = MAX_RETRIES,
    **kwargs
) -> AsyncIterator[str]:
    """Execute a streaming function with retry logic and exponential backoff."""
    last_error = None
    delay = RETRY_DELAY_SECONDS
    
    for attempt in range(max_retries + 1):
        try:
            async for token in func(*args, **kwargs):
                yield token
            return  # Success, exit retry loop
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_error = exc
            if attempt < max_retries:
                logger.warning(
                    "LLM request failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc
                )
                await asyncio.sleep(delay)
                delay *= RETRY_BACKOFF_MULTIPLIER
            else:
                logger.error("LLM request failed after %d retries: %s", max_retries, exc)
                yield f"*Error: AI provider unavailable after {max_retries} retries*"
        except Exception as exc:
            # Non-retryable errors, yield immediately
            logger.error("LLM request failed with non-retryable error: %s", exc)
            yield f"*Error: AI provider error: {exc}*"
            return


async def _detect_ollama_model() -> str | None:
    """Get the selected model from the provider manager to ensure consistency."""
    try:
        from dash_backend.llm.provider_manager import get_ollama_manager
        
        manager = get_ollama_manager()
        health = await manager.ensure_provider_ready()
        
        if health.configured_model and health.model_available:
            logger.info("Using provider manager selected model: %s", health.configured_model)
            return health.configured_model
        elif health.installed_models:
            # Use first available model if configured one is not available
            logger.info("Using first available model: %s", health.installed_models[0])
            return health.installed_models[0]
        else:
            logger.warning("No models available from provider manager")
            return None
    except Exception as exc:
        logger.warning("Failed to get model from provider manager: %s", exc)
        return None


async def stream_chat_response(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream a chat completion from the configured AI provider.

    Supports OpenAI-compatible APIs and Ollama.
    Yields content tokens as they arrive.
    Includes retry logic with exponential backoff for transient failures.
    """
    settings = get_settings()

    provider = settings.ai_provider.lower()
    logger.info("Using AI provider: %s", provider)

    if provider == "ollama":
        async for token in _retry_with_backoff(_stream_ollama, messages, model):
            yield token
    else:
        async for token in _retry_with_backoff(_stream_openai, messages, model):
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


class NativeAssistantResponse:
    """Native OpenAI tool_calls response container."""

    def __init__(self, *, assistant_text: str, tool_calls: list[dict[str, Any]]):
        self.assistant_text = assistant_text
        self.tool_calls = tool_calls


def _normalize_messages_for_ollama(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert OpenAI-style history into what Ollama /api/chat accepts.

    Differences that cause HTTP 400:
    - assistant.tool_calls entries must be {function:{name, arguments:object}}
      — no "id"/"type" wrappers and arguments must NOT be a JSON string.
    - role="tool" content must be a plain string.
    """
    normalized: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        if role == "assistant" and m.get("tool_calls"):
            entry: dict[str, Any] = {
                "role": "assistant",
                "content": m.get("content") or "",
                "tool_calls": [],
            }
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function", {}) or {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                entry["tool_calls"].append(
                    {"function": {"name": fn.get("name", ""), "arguments": args if isinstance(args, dict) else {}}}
                )
            normalized.append(entry)
        elif role == "tool":
            content = m.get("content")
            if not isinstance(content, str):
                try:
                    content = json.dumps(content)
                except Exception:
                    content = str(content)
            normalized.append({"role": "tool", "content": content})
        else:
            normalized.append(m)
    return normalized


async def _native_tool_calls_ollama(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    model: str | None,
) -> NativeAssistantResponse:
    """Ollama native function calling via /api/chat.

    Ollama returns tool_calls WITHOUT ids; the chat pipeline requires
    non-empty ids (OpenAI sequencing), so we synthesize stable ones.
    """
    settings = get_settings()
    validated_messages = validate_openai_message_history(messages)
    if len(validated_messages) != len(messages):
        logger.warning(
            "Dropped %d invalid tool messages before Ollama tool request",
            len(messages) - len(validated_messages),
        )
    payload_messages = _normalize_messages_for_ollama(validated_messages)

    payload: dict[str, Any] = {
        "model": model or settings.ai_model or settings.ollama_model,
        "messages": payload_messages,
        "stream": False,
        "tools": tools,
        "options": {"num_ctx": settings.ollama_num_ctx},
    }
    if not settings.ollama_thinking:
        payload["think"] = False
    # Keep the model resident between requests. A machine-level
    # OLLAMA_KEEP_ALIVE=0 would otherwise unload it after every call.
    if settings.ollama_keep_alive:
        payload["keep_alive"] = settings.ollama_keep_alive

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    message = data.get("message") or {}
    assistant_text = message.get("content") or ""

    # Strip hidden reasoning blocks from thinking models defensively.
    if "</think>" in assistant_text:
        assistant_text = assistant_text.split("</think>", 1)[1].strip()

    tool_calls: list[dict[str, Any]] = []
    for i, tc in enumerate(message.get("tool_calls") or []):
        fn = tc.get("function", {}) or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        tool_calls.append(
            {
                "id": tc.get("id") or f"call_{i}_{fn.get('name', 'tool')}",
                "type": "function",
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": json.dumps(args if isinstance(args, dict) else {}),
                },
            }
        )

    return NativeAssistantResponse(assistant_text=assistant_text, tool_calls=tool_calls)


async def stream_chat_completion_with_native_tool_calls(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]],
) -> AsyncIterator[tuple[str, Any]]:
    """Streaming variant of chat_completion_with_native_tool_calls (Ollama).

    Yields:
        ("token", str)      — incremental assistant text deltas as they are
                              generated, so clients see progress immediately.
        ("final", NativeAssistantResponse) — always yielded last, containing
                              the complete text plus any parsed tool_calls.

    Non-Ollama providers fall back to a single ("final", ...) event from the
    non-streaming implementation.
    """
    settings = get_settings()

    if (settings.ai_provider or "").lower() != "ollama":
        response = await chat_completion_with_native_tool_calls(messages, tools=tools)
        yield ("final", response)
        return

    validated_messages = validate_openai_message_history(messages)
    if len(validated_messages) != len(messages):
        logger.warning(
            "Dropped %d invalid tool messages before Ollama streaming request",
            len(messages) - len(validated_messages),
        )
    payload_messages = _normalize_messages_for_ollama(validated_messages)

    payload: dict[str, Any] = {
        "model": None,
        "messages": payload_messages,
        "stream": True,
        "tools": tools,
        "options": {"num_ctx": settings.ollama_num_ctx},
    }
    # Resolve model via provider manager for consistency with non-stream path.
    try:
        from dash_backend.llm.provider_manager import get_ollama_manager

        manager = get_ollama_manager()
        health = await manager.ensure_provider_ready()
        if health.configured_model and health.model_available:
            payload["model"] = health.configured_model
        elif health.installed_models:
            payload["model"] = health.installed_models[0]
    except Exception:
        logger.warning("Provider manager unavailable; using configured model", exc_info=True)
    if not payload["model"]:
        payload["model"] = settings.ai_model or settings.ollama_model or "llama3.2:3b"

    if not settings.ollama_thinking:
        payload["think"] = False
    if settings.ollama_keep_alive:
        payload["keep_alive"] = settings.ollama_keep_alive

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    text_parts: list[str] = []
    raw_tool_calls: list[dict[str, Any]] = []

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = chunk.get("message") or {}
                    delta = message.get("content")
                    if delta:
                        text_parts.append(delta)
                        yield ("token", delta)
                    for tc in message.get("tool_calls") or []:
                        raw_tool_calls.append(tc)
                    if chunk.get("done"):
                        break
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama streaming request failed: %s", exc)
        raise

    assistant_text = "".join(text_parts)
    if "</think>" in assistant_text:
        assistant_text = assistant_text.split("</think>", 1)[1].strip()

    tool_calls: list[dict[str, Any]] = []
    for i, tc in enumerate(raw_tool_calls):
        fn = tc.get("function", {}) or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        tool_calls.append(
            {
                "id": tc.get("id") or f"call_{i}_{fn.get('name', 'tool')}",
                "type": "function",
                "function": {
                    "name": fn.get("name", ""),
                    "arguments": json.dumps(args if isinstance(args, dict) else {}),
                },
            }
        )

    logger.info(
        "Ollama streamed completion: model=%s chars=%d tool_calls=%d",
        payload["model"],
        len(assistant_text),
        len(tool_calls),
    )
    yield ("final", NativeAssistantResponse(assistant_text=assistant_text, tool_calls=tool_calls))


async def chat_completion_with_native_tool_calls(
    messages: list[dict[str, str]],
    *,
    tools: list[dict[str, Any]],
    tool_choice: str | dict[str, Any] | None = None,
    model: str | None = None,
    force_provider: str | None = None,
) -> NativeAssistantResponse:

    """Return native tool_calls for the configured provider.

    - ollama  -> POST /api/chat with `tools` (native function calling)
    - openai  -> POST /v1/chat/completions with `tools`
    
    Args:
        force_provider: Override the configured provider ("ollama" or "openai").
                        Used by cloud_fallback to route to Gemini when available.
    """
    settings = get_settings()
    provider = (force_provider or settings.ai_provider or "ollama").lower()

    if provider == "ollama":
        return await _native_tool_calls_ollama(messages, tools, model)

    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("No OPENAI_API_KEY configured")

    base_url = settings.openai_base_url.rstrip("/")
    url = f"{base_url}/chat/completions"
    model_name = model or settings.ai_model or settings.openai_model

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Validate message history before sending to OpenAI/LiteLLM
    validated_messages = validate_openai_message_history(messages)
    if len(validated_messages) != len(messages):
        dropped = len(messages) - len(validated_messages)
        logger.warning("Dropped %d invalid tool messages before native tool call request", dropped)

    payload: dict[str, Any] = {
        "model": model_name,
        "messages": validated_messages,
        "stream": False,
        "tools": tools,
    }
    if tool_choice is not None:
        payload["tool_choice"] = tool_choice

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    choice0 = (data.get("choices") or [{}])[0]
    message = choice0.get("message") or {}

    assistant_text = message.get("content") or ""
    tool_calls = message.get("tool_calls") or []

    return NativeAssistantResponse(assistant_text=assistant_text, tool_calls=tool_calls)


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

    # Validate message history before sending to OpenAI/LiteLLM
    # This prevents the "Invalid parameter: messages with role 'tool' must be a response
    # to a preceding message with 'tool_calls'" error.
    validated_messages = validate_openai_message_history(messages)
    if len(validated_messages) != len(messages):
        dropped = len(messages) - len(validated_messages)
        logger.warning("Dropped %d invalid tool messages before OpenAI request", dropped)

    # Ollama low-memory optimization:
    # - keep context small
    # - avoid unnecessary GPU offload (let Ollama decide on CPU-only setups)
    # - keep streaming enabled
    # Note: Ollama ignores unknown fields; still safe across versions.
    payload = {
        "model": model_name,
        "messages": validated_messages,
        "stream": True,
        # keep generation short enough for limited VRAM/CPU
        "options": {
            "num_ctx": 1024,
            "num_predict": 256,
            # keep on CPU if possible (prevents GPU over-allocation on low VRAM)
            "num_gpu": 0,
        },
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
        yield "*My AI engine is taking too long to respond. Please try again.*"
    except httpx.RequestError as exc:
        logger.error("OpenAI API request failed: %s", exc)
        yield "*I can't reach my AI engine right now. I'm checking the connection.*"


async def _stream_ollama(
    messages: list[dict[str, str]],
    model: str | None = None,
) -> AsyncIterator[str]:

    """Stream from an Ollama instance with auto-detection of available models."""
    settings = get_settings()

    base_url = settings.ollama_base_url.rstrip("/")
    url = f"{base_url}/api/chat"

    # Model selection priority:
    # 1. Explicit model argument
    # 2. settings.ai_model if intentionally configured
    # Use provider manager to get the selected model (ensures consistency)
    try:
        from dash_backend.llm.provider_manager import get_ollama_manager
        manager = get_ollama_manager()
        health = await manager.ensure_provider_ready()
        if health.configured_model and health.model_available:
            model_name = health.configured_model
            logger.info("Using provider manager selected model: %s", model_name)
        elif health.installed_models:
            model_name = health.installed_models[0]
            logger.info("Using first available model from provider manager: %s", model_name)
        else:
            # Fallback to settings if provider manager fails
            if model:
                model_name = model
            elif settings.ai_model:
                model_name = settings.ai_model
            elif settings.ollama_model:
                model_name = settings.ollama_model
            else:
                model_name = "llama3.2:3b"  # Safe fallback
            logger.warning("Provider manager has no models, using fallback: %s", model_name)
    except Exception as exc:
        logger.warning("Failed to get model from provider manager, using settings: %s", exc)
        if model:
            model_name = model
        elif settings.ai_model:
            model_name = settings.ai_model
        elif settings.ollama_model:
            model_name = settings.ollama_model
        else:
            model_name = "llama3.2:3b"  # Safe fallback

    logger.info("Sending prompt to Ollama model: %s at %s", model_name, base_url)

    # Validate message history before sending to Ollama
    validated_messages = validate_openai_message_history(messages)
    if len(validated_messages) != len(messages):
        dropped = len(messages) - len(validated_messages)
        logger.warning("Dropped %d invalid tool messages before Ollama request", dropped)

    payload = {
        "model": model_name,
        "messages": validated_messages,
        "stream": True,
        "options": {
            # Configurable context window (memory/history must fit).
            "num_ctx": get_settings().ollama_num_ctx,
        },
    }
    # Thinking models (qwen3/deepseek-r1) burn tokens on hidden reasoning and
    # slow local inference massively. Disabled by default; ignored by models
    # without thinking support.
    if not get_settings().ollama_thinking:
        payload["think"] = False
    if get_settings().ollama_keep_alive:
        payload["keep_alive"] = get_settings().ollama_keep_alive

    # Retry logic for connection failures
    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
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
                        if response.status_code == 404:
                            yield "*I can't reach my AI engine right now. The configured model isn't available.*"
                        else:
                            yield "*I can't reach my AI engine right now. I'm checking the connection.*"
                        return

                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue

                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        content = chunk.get("message", {}).get("content", "")
                        if isinstance(content, str) and content:
                            yield content
                    return  # Success, exit retry loop

        except httpx.TimeoutException:
            logger.error("Ollama request timed out (attempt %d/%d)", attempt + 1, max_retries)
            if attempt == max_retries - 1:
                yield "*My AI engine is taking too long to respond. Please try again.*"
            else:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        except httpx.RequestError as exc:
            logger.error("Ollama request failed (attempt %d/%d): %s", attempt + 1, max_retries, exc)
            if attempt == max_retries - 1:
                yield "*I can't reach my AI engine right now. I'm checking the connection.*"
            else:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        except Exception as exc:
            logger.exception("Unexpected Ollama error (attempt %d/%d)", attempt + 1, max_retries)
            if attempt == max_retries - 1:
                yield "*Something went wrong with my AI engine. Please try again.*"
            else:
                await asyncio.sleep(retry_delay)
                retry_delay *= 2


def trim_history_for_tokens(history: list[dict[str, str]] | None, *, max_tokens: int = 2000) -> list[dict[str, str]]:
    """Trim conversation history to fit within an approximate token budget.

    This helper prefers to keep recent exchanges and attempts to preserve
    assistant messages and any entries that carry a 'token_count' field
    (which is trusted when present). When token counts are unavailable,
    a conservative word-based heuristic is used.

    Returns a trimmed history (oldest-first) suitable for LLM input.
    """
    if not history:
        return []

    # Compute token sums if token_count present, otherwise estimate by words
    entries = []
    for m in history:
        token_count = None
        if isinstance(m, dict) and isinstance(m.get("token_count"), int):
            token_count = int(m.get("token_count"))
        else:
            # conservative heuristic: 1 token ~= 0.75 words -> use words/0.75
            token_count = max(1, int(len(m.get("content", "").split()) * 1.4))
        entries.append((m, token_count))

    # Walk from newest to oldest, accumulating tokens until max_tokens reached
    kept = []
    total = 0
    for m, t in reversed(entries):
        # Always include assistant messages and any messages marked as important
        is_assistant = m.get("role") == "assistant"
        is_important = m.get("important", False)
        if total + t <= max_tokens or is_assistant or is_important:
            kept.append((m, t))
            total += t
        else:
            # stop adding older messages unless they are assistant/important
            continue

    # kept currently is newest->oldest; return oldest->newest
    kept.reverse()
    return [m for m, _ in kept]


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
        # Sanitize memory context before injection
        sanitized_memory = sanitize_memory_context(memory_context)
        system_parts.append("\n[USER MEMORY CONTEXT]")
        system_parts.append(sanitized_memory)
        system_parts.append("[/USER MEMORY CONTEXT]\n")

    if conversation_summary:
        # Sanitize conversation summary before injection
        sanitized_summary = sanitize_for_llm(conversation_summary, 2000)
        system_parts.append("\n[CONVERSATION SUMMARY]")
        system_parts.append(sanitized_summary)
        system_parts.append("[/CONVERSATION SUMMARY]\n")

    if system_parts:
        messages.append({"role": "system", "content": "\n".join(system_parts)})

    if history:
        messages.extend(history)

    if user_message:
        # Sanitize user message before injection
        sanitized_user_message = sanitize_for_llm(user_message)
        messages.append({"role": "user", "content": sanitized_user_message})

    # Validate the built messages to catch any orphan tool messages early
    messages = validate_openai_message_history(messages)

    return messages

