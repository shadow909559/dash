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
    chat_completion_with_native_tool_calls,
    chat_completion_with_tool_parsing,
)
from dash_backend.llm.tool_protocol import ToolProtocol, get_tool_protocol
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

    Uses chat_completion_with_tool_parsing() / chat_completion_with_native_tool_calls()
    to detect either assistant text/tool_call or a structured tool call.

    Only OPENAI_NATIVE message ordering is fixed here.
    """

    from dash_backend.tools.base_tool import ToolContext
    from dash_backend.tools.tool_manager import ToolCallRequest, get_tool_manager
    from dash_backend.tools.tool_result import ToolEvent, ToolStatus

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

    # Attempt to load RAG context and merge into memory_context. Keep failures non-fatal.
    try:
        from dash_backend.rag.service import retrieve_context as _retrieve_rag_context

        rag_ctx = await _retrieve_rag_context(session, user_id, query=msg.content if getattr(msg, "content", None) else None)
        if rag_ctx:
            if memory_context:
                memory_context = memory_context + "\n\n" + rag_ctx
            else:
                memory_context = rag_ctx
    except Exception as exc:
        logger.warning("Failed to load RAG context: %s", exc)

    # Agent selection: if the client supplied an agent_id, attempt to load
    # the agent config (system_prompt, allowed_tools). Failures are non-fatal.
    agent = None
    try:
        if getattr(msg, "agent_id", None):
            from dash_backend.agents.service import get_agent as _get_agent

            agent = await _get_agent(session, msg.agent_id)
    except Exception:
        logger.exception("Failed to load agent %s", getattr(msg, "agent_id", None))

    tool_manager = get_tool_manager()
    last_assistant_text = ""

    for step in range(MAX_TOOL_STEPS + 1):
        current_user_message = msg.content if step == 0 else ""

        # For OPENAI_NATIVE we maintain a single list; for CUSTOM_JSON we keep
        # the legacy behavior (no role='tool' messages).
        messages = build_chat_messages(
            system_prompt=DASH_SYSTEM_PROMPT,
            history=history,
            user_message=current_user_message,
            memory_context=memory_context,
            conversation_summary=conversation_summary,
        )

        try:
            protocol = get_tool_protocol()  # must be called exactly once

            if protocol == ToolProtocol.CUSTOM_JSON:
                # Preserve legacy CUSTOM_JSON behavior
                parsed = await chat_completion_with_tool_parsing(messages)

                if isinstance(parsed, ToolCall):
                    tool_call_request = ToolCallRequest(
                        tool_name=parsed.name,
                        arguments=parsed.arguments,
                        call_id=None,
                    )

                    context = ToolContext(
                        user_id=user_id,
                        conversation_id=str(msg.conversation_id) if msg.conversation_id else None,
                        request_id=msg.message_id,
                    )

                    tool_result_dict: dict[str, object] | None = None

                    try:
                        async for event_type, data in tool_manager.execute_tool_stream(
                            tool_call_request, context
                        ):
                            if event_type == "tool.started":
                                yield ChatTokenMessage(
                                    message_id=msg.message_id,
                                    content=f"\n[tool:{parsed.name}] started\n",
                                )
                            elif event_type == "tool.progress":
                                progress = data.get("summary") or ""
                                yield ChatTokenMessage(
                                    message_id=msg.message_id,
                                    content=f"[tool:{parsed.name}] {progress}\n",
                                )
                            elif event_type == "tool.finished":
                                tool_result_dict = data
                                yield ChatTokenMessage(
                                    message_id=msg.message_id,
                                    content=f"[tool:{parsed.name}] finished\n",
                                )
                            elif event_type == "tool.error":
                                tool_result_dict = data
                                err = (
                                    data.get("error_message")
                                    or data.get("error")
                                    or "Tool error"
                                )
                                yield ChatTokenMessage(
                                    message_id=msg.message_id,
                                    content=f"\n*Tool error ({parsed.name}): {err}*\n",
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
                        yield ChatDoneMessage(message_id=msg.message_id)
                        return

                    # Legacy behavior: do NOT append role='tool' messages.
                    # Continue loop to ask the model again.
                    continue

                # Assistant text
                if isinstance(parsed, AssistantResponse):
                    streamed_text = parsed.text or ""
                    last_assistant_text = streamed_text
                    chunk_size = 20
                    for i in range(0, len(streamed_text), chunk_size):
                        token = streamed_text[i : i + chunk_size]
                        yield ChatTokenMessage(message_id=msg.message_id, content=token)
                    yield ChatDoneMessage(message_id=msg.message_id)
                    break

                yield ChatDoneMessage(message_id=msg.message_id)
                break

            # OPENAI_NATIVE FIXED BRANCH
            native = await chat_completion_with_native_tool_calls(
                messages,
                tools=tool_manager.get_tool_definitions(),
            )

            # 1) Receive native assistant tool_calls
            tool_calls_native = native.tool_calls or []

            # 2) Append the assistant tool_calls message to messages history
            # Required structure: role='assistant', tool_calls, and content.
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls_native,
                    "content": native.assistant_text,
                }
            )

            # Keep history in sync with messages for the next iteration.
            history = messages
            last_assistant_text += native.assistant_text or ""

            # If no tool_calls, we are done.
            if not tool_calls_native:
                # stream assistant text chunks
                streamed_text = native.assistant_text or ""
                chunk_size = 20
                for i in range(0, len(streamed_text), chunk_size):
                    token = streamed_text[i : i + chunk_size]
                    yield ChatTokenMessage(message_id=msg.message_id, content=token)
                yield ChatDoneMessage(message_id=msg.message_id)
                break

            # 3) Call ToolManager.parse_tool_calls()
            # Guard: Azure/OpenAI requires tool_call_id to exactly match the preceding assistant.tool_calls[].id.
            # ToolCallRequest.call_id becomes "" if native id is missing; fail fast to avoid invalid history.
            for tc in tool_calls_native:
                if not tc.get("id"):
                    raise ValueError("Native tool call missing non-empty 'id' (required for tool_call_id matching)")

            parsed_tool_calls = tool_manager.parse_tool_calls(
                {
                    "message": {
                        "tool_calls": tool_calls_native,
                    }
                }
            )


            # 4) Execute each tool
            context = ToolContext(
                user_id=user_id,
                conversation_id=str(msg.conversation_id) if msg.conversation_id else None,
                request_id=msg.message_id,
            )

            for call in parsed_tool_calls:
                tool_result: object | None = None
                tool_result_dict: dict[str, object] | None = None

                try:
                    async for event_type, data in tool_manager.execute_tool_stream(
                        call, context
                    ):
                        if event_type == ToolEvent.STARTED.value or event_type == "tool.started":
                            yield ChatTokenMessage(
                                message_id=msg.message_id,
                                content=f"\n[tool:{call.tool_name}] started\n",
                            )
                        elif event_type == ToolEvent.PROGRESS.value or event_type == "tool.progress":
                            progress = data.get("summary") or ""
                            yield ChatTokenMessage(
                                message_id=msg.message_id,
                                content=f"[tool:{call.tool_name}] {progress}\n",
                            )
                        elif event_type == ToolEvent.FINISHED.value or event_type == "tool.finished":
                            tool_result_dict = data
                            tool_result = data
                            yield ChatTokenMessage(
                                message_id=msg.message_id,
                                content=f"[tool:{call.tool_name}] finished\n",
                            )
                        elif event_type == ToolEvent.ERROR.value or event_type == "tool.error":
                            tool_result_dict = data
                            err = data.get("error_message") or data.get("error") or "Tool error"
                            yield ChatTokenMessage(
                                message_id=msg.message_id,
                                content=f"\n*Tool error ({call.tool_name}): {err}*\n",
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

                if tool_result_dict is None:
                    yield ChatDoneMessage(message_id=msg.message_id)
                    return

                # 5) Append ToolManager.format_result_for_llm() output
                # ToolManager.execute_tool_stream yields data dict; we need ToolResult
                # instance to format for llm. We can reconstruct ToolResult from dict
                # via ToolResult.from_dict if available; otherwise format directly.
                # Here we rely on execute_tool_stream's ToolResult serialization.
                # ToolManager.format_result_for_llm expects ToolResult, so we call
                # ToolManager.execute_tool() instead for formatting.
                # But requirement says execute every tool using existing ToolExecutor.
                # We'll call execute_tool() which collects results using the same executor.

                final_result = await tool_manager.execute_tool(call, context)
                history.append(tool_manager.format_result_for_llm(call, final_result))

            # 6) Continue loop until assistant returns no tool_calls
            continue

        except Exception as exc:
            logger.exception("LLM tool-aware completion failed")
            yield ChatTokenMessage(
                message_id=msg.message_id,
                content=f"*Sorry, an error occurred: {exc}*",
            )
            yield ChatDoneMessage(message_id=msg.message_id)
            return

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

