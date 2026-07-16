"""WebSocket message handlers with memory and conversation integration."""

from __future__ import annotations

import json
from typing import AsyncIterator


from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.api.websocket.protocol import (
    AgentDoneMessage,
    AgentErrorMessage,
    AgentRunMessage,
    AgentStepMessage,
    ChatDoneMessage,
    ChatErrorMessage,
    ChatSendMessage,
    ChatTokenMessage,
    ToolErrorMessage,
    ToolFinishedMessage,
    ToolProgressMessage,
    ToolStartedMessage,
    VoiceSTTDoneMessage,
    VoiceSTTErrorMessage,
    VoiceSTTMessage,
    VoiceTTSDoneMessage,
    VoiceTTSErrorMessage,
    VoiceTTSMessage,
)

from dash_backend.chat.service import (
    get_conversation_messages,
    needs_summary,
    save_conversation_summary,
)
from dash_backend.llm.service import (
    AssistantResponse,
    ToolCall,
    build_chat_messages,
    chat_completion_with_tool_parsing,
)

from dash_backend.logging_config import get_logger

from dash_backend.memory.service import (
    build_memory_context,
    extract_memories_from_conversation,
    summarize_conversation,
)

logger = get_logger(__name__)

DASH_SYSTEM_PROMPT = (
    "You are DASH, a helpful, capable personal AI assistant. "
    "You are concise but friendly. Answer questions directly and accurately. "
    "When you don't know something, say so. "
    "You can help with coding, writing, analysis, and general knowledge. "
    "You have access to the user's memory and conversation history."
)


async def handle_chat_send(
    msg: ChatSendMessage,
    session: AsyncSession,
    user_id: str,
) -> AsyncIterator[object]:
    """Memory-aware chat handler with tool calling.

    Uses chat_completion_with_tool_parsing() to detect either assistant text
    or a structured tool call.

    Tool loop:
      - maximum 5 tool iterations
      - executes tools via existing ToolManager/ToolExecutor
      - streams tool lifecycle events
      - appends tool result into the LLM messages context
    """

    from dash_backend.tools.tool_manager import ToolCallRequest, get_tool_manager
    from dash_backend.tools.tool_result import ToolStatus, ToolEvent
    from dash_backend.tools.base_tool import ToolContext

    MAX_TOOL_STEPS = 5

    # Load previous messages if this is an existing conversation
    history: list[dict[str, str]] = []
    memory_context: str | None = None
    conversation_summary: str | None = None

    if msg.conversation_id:
        try:
            db_messages, total = await get_conversation_messages(
                session, msg.conversation_id, limit=200
            )
            for db_msg in db_messages:
                history.append(
                    {
                        "role": db_msg.role.value,
                        "content": db_msg.content,
                    }
                )

            if total >= 18:
                summary_text = await summarize_conversation(
                    session,
                    msg.conversation_id,
                    [{"role": m.role.value, "content": m.content} for m in db_messages[-10:]],
                )
                if summary_text:
                    conversation_summary = summary_text
        except Exception as exc:
            logger.warning("Failed to load conversation history: %s", exc)

    try:
        memory_context = await build_memory_context(session, user_id)
    except Exception as exc:
        logger.warning("Failed to load memory context: %s", exc)

    # We build the LLM message list for each step (system+history+current user/tool context)
    # For tool results we append a synthetic role='tool' message.
    tool_messages: list[dict[str, str]] = []

    tool_manager = get_tool_manager()

    last_assistant_text = ""

    for step in range(MAX_TOOL_STEPS + 1):
        # If we already got final assistant text, exit.
        current_user_message = msg.content if step == 0 else ""

        messages = build_chat_messages(
            system_prompt=DASH_SYSTEM_PROMPT,
            history=(history + tool_messages),
            user_message=current_user_message,
            memory_context=memory_context,
            conversation_summary=conversation_summary,
        )

        try:
            parsed = await chat_completion_with_tool_parsing(messages)
        except Exception as exc:
            logger.exception("LLM tool-aware completion failed")
            yield ChatTokenMessage(
                message_id=msg.message_id,
                content=f"*Sorry, an error occurred: {exc}*",
            )
            yield ChatDoneMessage(message_id=msg.message_id)
            return

        if isinstance(parsed, AssistantResponse):
            # Stream assistant response exactly like before (token-by-token)
            # We can’t stream tokens from the collected response; so we stream the
            # parsed text in chunks to preserve websocket “token” behavior.
            try:
                streamed_text = parsed.text or ""
                # chunk into small pieces to keep UI responsive
                chunk_size = 20
                for i in range(0, len(streamed_text), chunk_size):
                    token = streamed_text[i : i + chunk_size]
                    last_assistant_text += token
                    yield ChatTokenMessage(message_id=msg.message_id, content=token)
            except Exception:
                # Fallback: send whole text
                last_assistant_text = parsed.text or ""
                if last_assistant_text:
                    yield ChatTokenMessage(message_id=msg.message_id, content=last_assistant_text)

            yield ChatDoneMessage(message_id=msg.message_id)
            break

        if isinstance(parsed, ToolCall):
            tool_call = parsed

            tool_call_request = ToolCallRequest(
                tool_name=tool_call.name,
                arguments=tool_call.arguments,
                call_id=None,
            )

            context = ToolContext(
                user_id=user_id,
                conversation_id=str(msg.conversation_id) if msg.conversation_id else None,
                request_id=msg.message_id,
            )

            # Execute and stream tool lifecycle events
            tool_result_dict: dict[str, object] | None = None

            try:
                async for event_type, data in tool_manager.execute_tool_stream(
                    tool_call_request, context
                ):
                    if event_type == "tool.started":
                        yield ChatTokenMessage(
                            message_id=msg.message_id,
                            content=f"\n[tool:{tool_call.name}] started\n",
                        )
                    elif event_type == "tool.progress":
                        progress = data.get("summary") or ""
                        yield ChatTokenMessage(
                            message_id=msg.message_id,
                            content=f"[tool:{tool_call.name}] {progress}\n",
                        )
                    elif event_type == "tool.finished":
                        tool_result_dict = data
                        yield ChatTokenMessage(
                            message_id=msg.message_id,
                            content=f"[tool:{tool_call.name}] finished\n",
                        )
                    elif event_type == "tool.error":
                        tool_result_dict = data
                        # Surface tool errors in chat stream
                        err = data.get("error_message") or data.get("error") or "Tool error"
                        yield ChatTokenMessage(
                            message_id=msg.message_id,
                            content=f"\n*Tool error ({tool_call.name}): {err}*\n",
                        )

                        yield ChatDoneMessage(message_id=msg.message_id)
                        return
            except Exception as exc:
                logger.exception("Tool execution failed")
                yield ChatTokenMessage(
                    message_id=msg.message_id,
                    content=f"\n*Tool execution exception: {exc}*\n",
                )
                yield ChatDoneMessage(message_id=msg.message_id)
                return

            if not tool_result_dict:
                # Defensive: no result, stop.
                yield ChatDoneMessage(message_id=msg.message_id)
                return

            # Append tool result into LLM conversation history as role='tool'
            # ToolManager has a formatter but we only have tool_result_dict; format again.
            # ToolManager.format_result_for_llm expects ToolResult object.
            # Reconstruct minimal ToolResult-like structure.
            try:
                tool_status = tool_result_dict.get("status", ToolStatus.ERROR.value)
                # We'll stringify tool output in the 'content' field.
                tool_payload = {
                    "status": tool_status,
                    "output": tool_result_dict.get("output", {}),
                    "summary": tool_result_dict.get("summary", ""),
                    "error": tool_result_dict.get("error_message") if tool_result_dict.get("error_message") else None,
                    "duration_ms": tool_result_dict.get("duration_ms", 0.0),
                }
                tool_messages.append(
                    {
                        "role": "tool",
                        "content": json.dumps(tool_payload, indent=2),
                    }
                )
            except Exception as exc:
                logger.warning("Failed to append tool result to history: %s", exc)

            # Continue loop: ask LLM again.
            continue

    # Post-response: extract memories from the exchange
    try:
        exchange_messages = [
            {"role": "user", "content": msg.content},
            {"role": "assistant", "content": last_assistant_text},
        ]
        if msg.conversation_id:
            await extract_memories_from_conversation(
                session, user_id, msg.conversation_id, exchange_messages
            )
    except Exception as exc:
        logger.warning("Failed to extract memories: %s", exc)

    # Post-response: auto-summarize if needed
    if msg.conversation_id:
        try:
            if await needs_summary(session, msg.conversation_id):
                all_messages = history + [
                    {"role": "user", "content": msg.content},
                    {"role": "assistant", "content": last_assistant_text},
                ]
                summary = await summarize_conversation(
                    session, msg.conversation_id, all_messages
                )
                if summary:
                    await save_conversation_summary(
                        session,
                        msg.conversation_id,
                        summary,
                        message_count=len(all_messages) // 2,
                        token_count=len(last_assistant_text.split()),
                    )
        except Exception as exc:
            logger.warning("Failed to auto-summarize: %s", exc)



async def handle_agent_run(msg: AgentRunMessage) -> AsyncIterator[object]:
    """Handle agent execution requests."""
    yield AgentStepMessage(
        request_id=msg.request_id,
        step_index=0,
        output={"echo": msg.input},
    )
    yield AgentDoneMessage(request_id=msg.request_id, output={"result": msg.input})


async def handle_voice_stt(msg: VoiceSTTMessage) -> AsyncIterator[object]:
    """Handle speech-to-text requests."""
    yield VoiceSTTDoneMessage(request_id=msg.request_id, text="[stt-not-implemented]")


async def handle_voice_tts(msg: VoiceTTSMessage) -> AsyncIterator[object]:
    """Handle text-to-speech requests."""
    yield VoiceTTSDoneMessage(request_id=msg.request_id, audio_base64="")


async def safe_stream(stream: AsyncIterator[object], *, on_error) -> AsyncIterator[object]:
    """Wrap a stream with error handling."""
    try:
        async for item in stream:
            yield item
    except Exception as exc:
        yield on_error(str(exc))


def chat_error(message_id: str | None, error: str) -> ChatErrorMessage:
    return ChatErrorMessage(message_id=message_id, error=error)


def agent_error(request_id: str | None, error: str) -> AgentErrorMessage:
    return AgentErrorMessage(request_id=request_id, error=error)


def voice_stt_error(request_id: str, error: str) -> VoiceSTTErrorMessage:
    return VoiceSTTErrorMessage(request_id=request_id, error=error)


def voice_tts_error(request_id: str, error: str) -> VoiceTTSErrorMessage:
    return VoiceTTSErrorMessage(request_id=request_id, error=error)