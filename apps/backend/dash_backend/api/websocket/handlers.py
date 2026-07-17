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
from dash_backend.security.rate_limiter import websocket_rate_limit_user
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

    # Apply websocket per-user rate limiting before doing heavy work
    try:
        await websocket_rate_limit_user(user_id)
    except RuntimeError:
        # Rate limited: return a safe message to client and end the stream
        logger.warning("Dropping websocket message due to rate limit for user %s", user_id)
        yield ChatTokenMessage(message_id=msg.message_id, content="*Rate limit exceeded, please slow down.*")
        yield ChatDoneMessage(message_id=msg.message_id)
        return

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
                # include token_count when available for better trimming
                history.append(
                    {
                        "role": db_msg.role.value,
                        "content": db_msg.content,
                        "token_count": getattr(db_msg, "token_count", None),
                    }
                )

            # If conversation is long, build a short extractive summary for recent messages
            if total >= 18:
                recent_msgs = [{"role": m.role.value, "content": m.content} for m in db_messages[-10:]]
                summary_text = await summarize_conversation(session, msg.conversation_id, recent_msgs)
                if summary_text:
                    conversation_summary = summary_text
        except Exception:
            logger.exception("Failed to load conversation history")

    # Trim history to an approximate token budget to keep prompts small
    try:
        from dash_backend.llm.service import trim_history_for_tokens

        history = trim_history_for_tokens(history, max_tokens=1800)
    except Exception:
        # Trimming is best-effort; if it fails, proceed with full history
        logger.exception("Failed to trim conversation history")

    try:
        memory_context = await build_memory_context(session, user_id)
    except Exception:
        logger.exception("Failed to load memory context")

    # Attempt to load RAG context and merge into memory_context. Keep failures non-fatal.
    try:
        from dash_backend.rag.service import retrieve_context as _retrieve_rag_context

        rag_ctx = await _retrieve_rag_context(session, user_id, query=msg.content if getattr(msg, "content", None) else None)
        if rag_ctx:
            if memory_context:
                memory_context = memory_context + "\n\n" + rag_ctx
            else:
                memory_context = rag_ctx
    except Exception:
        logger.exception("Failed to load RAG context")

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
        # Build the system prompt. If an agent is selected and has a system_prompt,
        # prepend it to the default DASH_SYSTEM_PROMPT so agent behavior is applied.
        system_prompt = DASH_SYSTEM_PROMPT
        try:
            if agent and getattr(agent, "system_prompt", None):
                system_prompt = f"{agent.system_prompt}\n\n{DASH_SYSTEM_PROMPT}"
        except Exception:
            # If agent is malformed, fallback to DASH_SYSTEM_PROMPT
            system_prompt = DASH_SYSTEM_PROMPT

        messages = build_chat_messages(
            system_prompt=system_prompt,
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
                    except Exception:
                        # Log full exception server-side, but return a safe message to client.
                        logger.exception("Tool execution failed during CUSTOM_JSON handling")
                        yield ChatTokenMessage(
                            message_id=msg.message_id,
                            content="\n*Tool execution exception: An internal error occurred.*\n",
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
            # If an agent restricts allowed_tools, filter the tool definitions accordingly
            tool_defs = tool_manager.get_tool_definitions()
            if agent and getattr(agent, "allowed_tools", None):
                allowed = set(agent.allowed_tools or [])

                def _tool_name(td: dict) -> str:
                    # OpenAI-compatible format: td['function']['name']
                    try:
                        return td.get("function", {}).get("name") or td.get("name") or ""
                    except Exception:
                        return ""

                tool_defs = [td for td in tool_defs if _tool_name(td) in allowed]

            native = await chat_completion_with_native_tool_calls(
                messages,
                tools=tool_defs,
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
                except Exception:
                    # Log full exception server-side, but return safe message to client
                    logger.exception("Tool execution failed during native tool execution")
                    yield ChatTokenMessage(
                        message_id=msg.message_id,
                        content="\n*Tool execution exception: An internal error occurred.*\n",
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

                # Execute tool with timeout and a single retry on timeout
                from dash_backend.config import get_settings
                import asyncio

                settings = get_settings()
                timeout = getattr(settings, "tool_execution_timeout_seconds", 60)

                try:
                    start_ts = asyncio.get_event_loop().time()
                    try:
                        final_result = await asyncio.wait_for(tool_manager.execute_tool(call, context), timeout=timeout)
                    except asyncio.TimeoutError:
                        # Retry once quickly (transient provider/network blip)
                        logger.warning("Tool execution timed out for %s, retrying once", call.tool_name)
                        try:
                            final_result = await asyncio.wait_for(tool_manager.execute_tool(call, context), timeout=timeout)
                        except asyncio.TimeoutError:
                            logger.exception("Tool execution timed out after retry for %s", call.tool_name)
                            yield ChatTokenMessage(
                                message_id=msg.message_id,
                                content="\n*Tool execution timed out.*\n",
                            )
                            yield ChatDoneMessage(message_id=msg.message_id)
                            return
                    end_ts = asyncio.get_event_loop().time()
                    elapsed_ms = int((end_ts - start_ts) * 1000)
                    logger.info("Tool executed: user=%s tool=%s duration_ms=%d", user_id, call.tool_name, elapsed_ms)

                    # Enforce result size limits (avoid giant payloads to the LLM)
                    try:
                        formatted = tool_manager.format_result_for_llm(call, final_result)
                        # Truncate long content fields safely
                        if isinstance(formatted, dict):
                            if "content" in formatted and isinstance(formatted["content"], str) and len(formatted["content"]) > 2000:
                                formatted["content"] = formatted["content"][:2000] + "..."
                        history.append(formatted)
                    except Exception:
                        # Fallback: append a minimal result description
                        history.append({"role": "tool", "content": f"[tool:{call.tool_name}] completed (truncated)"})
                except Exception:
                    logger.exception("Tool execution failed during native tool execution")
                    yield ChatTokenMessage(
                        message_id=msg.message_id,
                        content="\n*Tool execution exception: An internal error occurred.*\n",
                    )
                    yield ChatDoneMessage(message_id=msg.message_id)
                    return

            # 6) Continue loop until assistant returns no tool_calls
            continue

        except Exception:
            # Log full exception server-side, but return a safe generic message to the client
            logger.exception("LLM tool-aware completion failed")
            yield ChatTokenMessage(
                message_id=msg.message_id,
                content="*Sorry, an internal error occurred while processing your request.*",
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
    except Exception:
        logger.exception("Failed to extract memories")

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
        except Exception:
            logger.exception("Failed to auto-summarize")


async def handle_agent_run(msg: AgentRunMessage) -> AsyncIterator[object]:
    """Handle agent execution requests."""
    yield AgentStepMessage(
        request_id=msg.request_id,
        step_index=0,
        output={"echo": msg.input},
    )
    yield AgentDoneMessage(request_id=msg.request_id, output={"result": msg.input})


async def handle_voice_stt(msg: VoiceSTTMessage, session: AsyncSession, user_id: str) -> AsyncIterator[object]:
    """Handle speech-to-text requests: transcribe audio and forward to chat pipeline."""
    import base64
    import uuid

    from dash_backend.voice import transcribe_audio
    from dash_backend.api.websocket.protocol import ChatSendMessage
    from dash_backend.chat.service import add_message, create_conversation, get_conversation
    from dash_backend.db.session import AsyncSessionLocal
    from dash_backend.db.models.message import MessageRole

    # Decode audio
    try:
        audio_bytes = base64.b64decode(msg.audio_base64)
    except Exception as exc:
        logger.exception("Failed to decode audio for STT: %s", exc)
        yield voice_stt_error(msg.request_id, "Invalid audio payload")
        return

    # Transcribe (provider-agnostic)
    try:
        transcript = await transcribe_audio(audio_bytes, user_id=user_id, store=False)
    except Exception as exc:
        logger.exception("STT provider failed: %s", exc)
        yield voice_stt_error(msg.request_id, "Speech-to-text failed")
        return

    # Send STT done message
    yield VoiceSTTDoneMessage(request_id=msg.request_id, text=transcript)

    # Parse transcript for quick command routing via SkillRouter (non-breaking enhancement)
    try:
        from dash_backend.voice_system.parser import parse_command
        from dash_backend.skills.skill_router import SkillRouter, SkillContext
        parsed = parse_command(transcript)
        # If the parser detected a concrete intent (not llm_fallback), route to skill
        if parsed and parsed.get("intent") and parsed.get("intent") != "llm_fallback":
            router = SkillRouter()
            ctx = SkillContext(user_id=user_id, session_id=None, extra={})
            try:
                skill_res = await router.route(parsed.get("intent"), parsed.get("args", {}), ctx)
                # Emit a lightweight message to the client with the skill result
                try:
                    # Prefer structured step message when available
                    yield AgentStepMessage(request_id=msg.request_id, step_index=0, output={"skill": parsed.get("intent"), "result": skill_res})
                except Exception:
                    # Fallback to chat token message
                    yield ChatTokenMessage(message_id=str(uuid.uuid4()), content=f"[skill:{parsed.get('intent')}] {skill_res}")
            except Exception:
                logger.exception("SkillRouter routing failed for transcript")
    except Exception:
        # Parsing/routing is optional and non-fatal
        logger.exception("Failed to parse/route voice transcript")

    # Forward transcript into the existing chat pipeline as a user message
    # We'll create or reuse a conversation similar to chat.send handling
    try:
        conversation = None
        # create a new conversation for this voice interaction
        conversation = await create_conversation(session=session, user_id=user_id)

        # Persist the user message
        await add_message(session=session, conversation_id=conversation.id, role=MessageRole.USER, content=transcript)

        # Build ChatSendMessage and call chat handler
        chat_msg = ChatSendMessage(conversation_id=conversation.id, message_id=str(uuid.uuid4()), content=transcript)

        async for event in handle_chat_send(chat_msg, session=session, user_id=user_id):
            yield event

    except Exception:
        logger.exception("Failed to forward STT to chat pipeline")
        # Non-fatal: continue
        return


async def handle_voice_tts(msg: VoiceTTSMessage, session: AsyncSession, user_id: str) -> AsyncIterator[object]:
    """Handle text-to-speech requests: synthesize text and return audio_base64."""
    from dash_backend.voice import synthesize_text

    try:
        audio_b64 = await synthesize_text(msg.text, user_id=user_id)
    except Exception as exc:
        logger.exception("TTS provider failed: %s", exc)
        yield voice_tts_error(msg.request_id, "Text-to-speech failed")
        return

    # Return done message with base64 audio (may be empty if provider not configured)
    yield VoiceTTSDoneMessage(request_id=msg.request_id, audio_base64=audio_b64)


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

