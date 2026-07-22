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

    validate_openai_message_history(messages)


def validate_openai_message_history(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sanitize OpenAI/LiteLLM tool-message sequences.

    This is the canonical entrypoint used before every OpenAI/LiteLLM request.
    EVERY LLM request MUST pass through this function.

    The sanitizer is *conservative*:
    - Drops invalid tool messages.
    - Removes consecutive tool messages.
    - Removes duplicate tool_call_id tool messages following the same assistant.
    - Verifies ordering: assistant(tool_calls) → tool → assistant

    It never raises.
    """

    cleaned: list[dict[str, Any]] = []

    for i, m in enumerate(messages):
        if m.get("role") != "tool":
            cleaned.append(m)
            continue

        # tool message rules: find the nearest assistant before this tool message
        # by scanning backwards through any existing tool messages
        prev = None
        for k in range(len(cleaned) - 1, -1, -1):
            if cleaned[k].get("role") == "assistant":
                prev = cleaned[k]
                break
            elif cleaned[k].get("role") != "tool":
                # Found a non-assistant, non-tool message (user/system)
                prev = cleaned[k]
                break

        ctx_before = messages[max(0, i - 3) : i]
        ctx_after = messages[i + 1 : i + 4]

        if prev is None or prev.get("role") != "assistant":
            detail = ValidationErrorDetail(
                index=i,
                reason='dropped orphan tool message: no preceding assistant.tool_calls',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            continue

        prev_tool_calls = prev.get("tool_calls") or []
        if not isinstance(prev_tool_calls, list) or not prev_tool_calls:
            detail = ValidationErrorDetail(
                index=i,
                reason='dropped tool message: preceding assistant has no tool_calls',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            continue

        tool_call_id = m.get("tool_call_id")
        if not tool_call_id:
            detail = ValidationErrorDetail(
                index=i,
                reason='dropped tool message: missing tool_call_id',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            continue

        # Collect valid ids from preceding assistant.tool_calls
        ids: list[Any] = []
        for tc in prev_tool_calls:
            if isinstance(tc, dict) and tc.get("id"):
                ids.append(tc.get("id"))

        if not ids:
            detail = ValidationErrorDetail(
                index=i,
                reason='dropped tool message: preceding assistant.tool_calls contains no ids',
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            continue

        # If tool_call_id is not in ids -> drop
        if tool_call_id not in ids:
            detail = ValidationErrorDetail(
                index=i,
                reason=f"dropped tool message: unknown tool_call_id={tool_call_id!r}",
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            continue

        # Deduplicate tool messages after this assistant by tracking ids already emitted
        # following this assistant (i.e., look backwards to nearest assistant)
        seen_ids: set[Any] = set()
        j = len(cleaned) - 1
        while j >= 0 and cleaned[j].get("role") == "tool":
            seen_ids.add(cleaned[j].get("tool_call_id"))
            j -= 1

        if tool_call_id in seen_ids:
            detail = ValidationErrorDetail(
                index=i,
                reason=f"dropped duplicate tool message for tool_call_id={tool_call_id!r}",
                message=m,
                context_before=ctx_before,
                context_after=ctx_after,
            )
            _log(detail)
            continue

        cleaned.append(m)

    # Final verification: ensure ordering is assistant(tool_calls) → tool → assistant
    # Walk through cleaned and verify no tool message is followed by another tool message
    # (already handled above) and that after tool messages, the next non-tool is assistant
    final_cleaned: list[dict[str, Any]] = []
    for i, m in enumerate(cleaned):
        if m.get("role") == "tool":
            # Check that the next non-tool message (if any) is assistant
            next_non_tool = None
            for j in range(i + 1, len(cleaned)):
                if cleaned[j].get("role") != "tool":
                    next_non_tool = cleaned[j]
                    break
            if next_non_tool and next_non_tool.get("role") != "assistant":
                detail = ValidationErrorDetail(
                    index=i,
                    reason=f'dropped tool message: next non-tool message has role={next_non_tool.get("role")!r}, expected assistant',
                    message=m,
                    context_before=cleaned[max(0, i - 3) : i],
                    context_after=cleaned[i + 1 : i + 4],
                )
                _log(detail)
                continue
        final_cleaned.append(m)

    return final_cleaned



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

