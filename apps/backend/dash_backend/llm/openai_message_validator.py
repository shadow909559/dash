from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class OpenAIMessageValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationErrorDetail:
    index: int
    reason: str
    message: dict[str, Any]
    context_before: list[dict[str, Any]]
    context_after: list[dict[str, Any]]


def validate_openai_messages(messages: list[dict[str, Any]]) -> None:
    """Validate OpenAI-compatible message sequencing for tool calling.

    Rules enforced (LiteLLM/OpenAI semantics):
    - If a message has role == "tool", it must be preceded by an assistant message
      that contains a tool_calls array.
    - tool_call_id must exist and match one of the preceding assistant tool_calls ids.
    - tool_call_id must not be duplicated within the same preceding assistant message.
    """

    for i, m in enumerate(messages):

        if m.get("role") != "tool":
            continue

        prev = messages[i - 1] if i > 0 else None
        ctx_before = messages[max(0, i - 3) : i]
        ctx_after = messages[i + 1 : i + 4]

        if i == 0 or prev is None:
            detail = ValidationErrorDetail(
                index=i,
                reason='tool message at index 0 has no preceding assistant.tool_calls',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)

        if prev.get("role") != "assistant":
            detail = ValidationErrorDetail(
                index=i,
                reason='tool message must follow an assistant message (role="assistant")',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)

        prev_tool_calls = prev.get("tool_calls") or []
        if not isinstance(prev_tool_calls, list) or not prev_tool_calls:
            detail = ValidationErrorDetail(
                index=i,
                reason='assistant message preceding tool message has no tool_calls',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)

        tool_call_id = m.get("tool_call_id")
        if not tool_call_id:
            detail = ValidationErrorDetail(
                index=i,
                reason='tool message missing tool_call_id',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)

        ids = []
        for tc in prev_tool_calls:
            if isinstance(tc, dict) and tc.get("id"):
                ids.append(tc.get("id"))

        if not ids:
            detail = ValidationErrorDetail(
                index=i,
                reason='assistant.tool_calls contains no entries with id',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)

        if len(ids) != len(set(ids)):
            # Duplicate tool_call ids within same assistant tool_calls are invalid.
            dupes = [x for x in set(ids) if ids.count(x) > 1]
            detail = ValidationErrorDetail(
                index=i,
                reason=f'duplicate tool_call ids within assistant.tool_calls: {dupes}',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)

        if tool_call_id not in ids:
            detail = ValidationErrorDetail(
                index=i,
                reason=f'tool_call_id={tool_call_id!r} does not match any id in preceding assistant.tool_calls',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            raise OpenAIMessageValidationError(detail.reason)


def _log(detail: ValidationErrorDetail) -> None:
    # Log exactly why it failed.
    logger.error(
        "OpenAI tool message validation failed: index=%s reason=%s tool_call_id=%r message=%s context_before=%s context_after=%s",
        detail.index,
        detail.reason,
        detail.message.get("tool_call_id"),
        detail.message,
        detail.context_before,
        detail.context_after,
    )

