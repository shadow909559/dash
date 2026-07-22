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
    - model: str | None
    - error: str | None
    - latency_ms: float | None
    """
    settings = get_settings()
    provider = settings.ai_provider.lower()
    
    result = {
        "healthy": False,
        "provider": provider,
        "model": None,
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
                    result["healthy"] = True
                    result["model"] = models[0].get("name") if models else None
                    result["latency_ms"] = latency_ms
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
                    result["model"] = settings.ai_model or settings.openai_model
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


async def chat_completion_with_native_tool_calls(
    messages: list[dict[str, str]],
    *,
    tools: list[dict[str, Any]],
    tool_choice: str | dict[str, Any] | None = None,
    model: str | None = None,
) -> NativeAssistantResponse:

    """Call OpenAI-compatible /chat/completions and return native tool_calls.

    This path intentionally does NOT use custom JSON parsing.
    """

    settings = get_settings()

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
            # Smaller context to fit limited RAM/VRAM.
            "num_ctx": 1024,
        },
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
                    if isinstance(content, str) and content:
                        yield content


    except httpx.TimeoutException:
        logger.error("Ollama request timed out")
        yield "*Error: AI provider request timed out*"
    except httpx.RequestError as exc:
        logger.error("Ollama request failed: %s", exc)
        yield f"*Error: Could not reach Ollama: {exc}*"


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

