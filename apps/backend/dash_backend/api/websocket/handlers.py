"""WebSocket message handlers with memory and conversation integration."""

from __future__ import annotations

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
    ToolConfirmationRequiredMessage,
    VoiceSTTDoneMessage,
    VoiceSTTErrorMessage,
    VoiceSTTMessage,
    VoiceTTSDoneMessage,
    VoiceTTSErrorMessage,
    VoiceTTSMessage,
    PhoneStateMessage,
    PhoneClipboardGetMessage,
    PhoneClipboardSetMessage,
    PhoneVolumeGetMessage,
    PhoneVolumeSetMessage,
    PhoneVolumeMuteMessage,
    PhoneFlashlightToggleMessage,
    PhoneNotificationsGetMessage,
    PhoneNotificationsClearMessage,
    PhoneAppsGetMessage,
    PhoneAppsOpenMessage,
    PhoneMediaPlayMessage,
    PhoneMediaPauseMessage,
    PhoneMediaNextMessage,
    PhoneMediaPreviousMessage,
    DesktopMouseMoveMessage,
    DesktopMouseClickMessage,
    DesktopMouseScrollMessage,
    DesktopKeyboardTypeMessage,
    DesktopKeyboardPressMessage,
    DesktopKeyboardHotkeyMessage,
    DesktopPowerShutdownMessage,
    DesktopPowerRestartMessage,
    DesktopPowerLockMessage,
    DesktopPowerSleepMessage,
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
    stream_chat_completion_with_native_tool_calls,
)
from dash_backend.llm.tool_protocol import ToolProtocol, get_tool_protocol
from dash_backend.logging_config import get_logger
from dash_backend.security.rate_limiter import websocket_rate_limit_user
from dash_backend.memory.service import (
    build_memory_context,
    extract_memories_from_conversation,
    summarize_conversation,
)
from dash_backend.db.session import AsyncSessionLocal

import asyncio

logger = get_logger(__name__)

DASH_SYSTEM_PROMPT = (
    "You are DASH, a helpful, capable personal AI assistant. "
    "You are concise but friendly. Answer questions directly and accurately. "
    "When you don't know something, say so. "
    "You can help with coding, writing, analysis, and general knowledge. "
    "You have access to the user's memory and conversation history."
)

VOICE_SYSTEM_PROMPT = (
    "You are DASH, a personal AI assistant speaking through a phone speaker. "
    "RULES FOR VOICE MODE: "
    "1. Reply in 1-3 short sentences maximum. Be direct and natural. "
    "2. Never use bullet points, markdown, code blocks, or formatting. "
    "3. Speak like a knowledgeable friend, not a chatbot. "
    "4. For status checks, say the key numbers only (e.g. CPU is at 30 percent, RAM at 85). "
    "5. For commands, confirm briefly (e.g. Done, locked your PC). "
    "6. Never say Heres, Below, or display formatting — just speak naturally. "
    "7. Keep responses under 30 words when possible."
)


async def execute_tool_exactly_once(
    tool_manager: object,
    call: object,
    context: object,
    timeout_seconds: float,
) -> tuple[list[str], object | None, bool]:
    """Execute ONE logical tool call exactly once via the streaming executor.

    The final streamed event already contains the complete ToolResult, so the
    result is reconstructed from the stream instead of running the tool again
    (the previous implementation executed side-effecting tools twice, three
    times with the timeout retry).

    Returns ``(chat_lines, final_tool_result, aborted)`` where ``aborted``
    indicates an error/timeout/no-result and the chat turn should end.
    """
    from dash_backend.tools.tool_result import ToolEvent, ToolResult

    lines: list[str] = []
    final_data: dict | None = None
    stream = tool_manager.execute_tool_stream(call, context).__aiter__()  # type: ignore[attr-defined]

    while True:
        try:
            event_type, data = await asyncio.wait_for(stream.__anext__(), timeout=timeout_seconds)
        except StopAsyncIteration:
            break
        except asyncio.TimeoutError:
            try:
                await stream.aclose()
            except Exception:
                pass
            logger.warning("Tool execution timed out after %.0fs: %s", timeout_seconds, getattr(call, "tool_name", "?"))
            lines.append("\n*Tool execution timed out.*\n")
            return lines, None, True

        if event_type == ToolEvent.STARTED.value or event_type == "tool.started":
            lines.append(f"\n[tool:{getattr(call, 'tool_name', '?')}] started\n")
        elif event_type == ToolEvent.CONFIRMATION_REQUIRED.value or event_type == "tool.confirmation_required":
            # Surface the pending confirmation (with its token) to the caller
            # instead of swallowing it: the user must be able to approve.
            return lines, ToolResult.from_dict(data), False
        elif event_type == ToolEvent.PROGRESS.value or event_type == "tool.progress":
            progress = data.get("summary") or ""
            if progress:
                lines.append(f"[tool:{getattr(call, 'tool_name', '?')}] {progress}\n")
        elif event_type == ToolEvent.FINISHED.value or event_type == "tool.finished":
            lines.append(f"[tool:{getattr(call, 'tool_name', '?')}] finished\n")
            final_data = data
        elif event_type == ToolEvent.ERROR.value or event_type == "tool.error":
            err = data.get("error_message") or data.get("error") or "Tool error"
            lines.append(f"\n*Tool error ({getattr(call, 'tool_name', '?')}): {err}*\n")
            return lines, ToolResult.from_dict(data), True
        else:
            summary = data.get("summary") or str(event_type)
            lines.append(f"[tool:{getattr(call, 'tool_name', '?')}] {summary}\n")

    if final_data is None:
        lines.append("\n*Tool execution produced no result.*\n")
        return lines, None, True
    return lines, ToolResult.from_dict(final_data), False


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
    from dash_backend.tools.tool_result import ToolEvent

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
        # Pass the user message as query for semantic memory retrieval
        memory_context = await build_memory_context(session, user_id, query=msg.content)
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
        base_prompt = VOICE_SYSTEM_PROMPT if getattr(msg, "voice_mode", False) else DASH_SYSTEM_PROMPT
        system_prompt = base_prompt
        try:
            if agent and getattr(agent, "system_prompt", None):
                system_prompt = f"{agent.system_prompt}\n\n{DASH_SYSTEM_PROMPT}"
        except Exception:
            # If agent is malformed, fallback to base prompt
            system_prompt = base_prompt

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
                                # Send notification for tool start
                                try:
                                    from dash_backend.api.routes.notifications import send_notification
                                    await send_notification(user_id, f"Tool Started: {parsed.name}", "Processing your request...", "info")
                                except Exception:
                                    logger.exception("Failed to send tool start notification")
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
                                # Send notification for tool completion
                                try:
                                    from dash_backend.api.routes.notifications import send_notification
                                    await send_notification(user_id, f"Tool Complete: {parsed.name}", "Task completed successfully", "success")
                                except Exception:
                                    logger.exception("Failed to send tool completion notification")
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
                                # Send notification for tool error
                                try:
                                    from dash_backend.api.routes.notifications import send_notification
                                    await send_notification(user_id, f"Tool Error: {parsed.name}", err, "error")
                                except Exception:
                                    logger.exception("Failed to send tool error notification")
                                yield ChatDoneMessage(message_id=msg.message_id)
                                return
                    except Exception:
                        # Log full exception server-side, but return a safe message to client.
                        logger.exception("Tool execution failed during CUSTOM_JSON handling")
                        yield ChatTokenMessage(
                            message_id=msg.message_id,
                            content="\n*Tool execution exception: An internal error occurred.*\n",
                        )
                        # Send notification for exception
                        try:
                            from dash_backend.api.routes.notifications import send_notification
                            await send_notification(user_id, "Tool Execution Failed", "An internal error occurred", "error")
                        except Exception:
                            logger.exception("Failed to send tool exception notification")
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
            tool_defs = tool_manager.select_tool_definitions(
                msg.content if step == 0 else (history[-1].get("content", "") if history else "")
            )
            # Skip tools for small models (<3B) that can't handle function calling — they output
            # tool-call JSON instead of natural text, which confuses the UI.
            try:
                from dash_backend.config import get_settings as _cfg
                _model_name = (_cfg().ollama_model or "").lower()
                _is_small = any(s in _model_name for s in ("1b", ":1b", "0.5b", ":3b"))
                if _is_small:
                    tool_defs = []
            except Exception:
                pass
            if agent and getattr(agent, "allowed_tools", None):
                allowed = set(agent.allowed_tools or [])

                def _tool_name(td: dict) -> str:
                    # OpenAI-compatible format: td['function']['name']
                    try:
                        return td.get("function", {}).get("name") or td.get("name") or ""
                    except Exception:
                        return ""

                tool_defs = [td for td in tool_defs if _tool_name(td) in allowed]

            # Stream the completion so clients receive tokens as they are
            # generated instead of waiting for the full response. Tool calls
            # arrive in the final ("final", ...) event.
            streamed_any_token = False
            text_parts: list[str] = []
            native = None
            async for kind, payload in stream_chat_completion_with_native_tool_calls(
                messages,
                tools=tool_defs,
            ):
                if kind == "token":
                    streamed_any_token = True
                    text_parts.append(payload)
                    yield ChatTokenMessage(message_id=msg.message_id, content=payload)
                elif kind == "final":
                    native = payload

            if native is None:  # defensive: generator must always yield final
                raise RuntimeError("LLM stream ended without a final response")

            # Reconcile streamed text with the authoritative final response
            # (thinking blocks may have been stripped from assistant_text).
            native_text = native.assistant_text or ""
            if streamed_any_token and "".join(text_parts) != native_text:
                pass  # keep already-emitted tokens; history uses final text

            last_assistant_text += native_text

            # 1) Receive native assistant tool_calls
            tool_calls_native = native.tool_calls or []

            # 2) Append the assistant tool_calls message to messages history
            # Required structure: role='assistant', tool_calls, and content.
            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": tool_calls_native,
                    "content": native_text,
                }
            )

            # Keep history in sync with messages for the next iteration.
            history = messages

            # If no tool_calls, we are done — tokens were already streamed.
            if not tool_calls_native:
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


            # 4) Execute each tool EXACTLY ONCE via the streaming executor.
            #    The final streamed event carries the complete ToolResult; it is
            #    reused for LLM formatting (never re-executed, never retried —
            #    side-effecting tools must not run multiple times).
            context = ToolContext(
                user_id=user_id,
                conversation_id=str(msg.conversation_id) if msg.conversation_id else None,
                request_id=msg.message_id,
            )

            from dash_backend.config import get_settings

            settings = get_settings()
            timeout = float(getattr(settings, "tool_execution_timeout_seconds", 60))

            for call in parsed_tool_calls:
                start_ts = asyncio.get_event_loop().time()
                try:
                    chat_lines, final_result, aborted = await execute_tool_exactly_once(
                        tool_manager, call, context, timeout
                    )
                except Exception:
                    # Log full exception server-side, but return safe message to client
                    logger.exception("Tool execution failed during native tool execution")
                    yield ChatTokenMessage(
                        message_id=msg.message_id,
                        content="\n*Tool execution exception: An internal error occurred.*\n",
                    )
                    yield ChatDoneMessage(message_id=msg.message_id)
                    return

                elapsed_ms = int((asyncio.get_event_loop().time() - start_ts) * 1000)
                logger.info("Tool executed once: user=%s tool=%s duration_ms=%d", user_id, call.tool_name, elapsed_ms)

                for line in chat_lines:
                    yield ChatTokenMessage(message_id=msg.message_id, content=line)

                # Pending user approval: hand the confirmation token to the
                # client so it can approve/reject via tool.confirmed/tool.rejected.
                if (
                    final_result is not None
                    and getattr(final_result, "status", None) is not None
                    and getattr(final_result.status, "value", "") == "pending_confirmation"
                ):
                    yield ToolConfirmationRequiredMessage(
                        message_id=msg.message_id,
                        tool_name=getattr(final_result, "tool_name", "") or getattr(call, "tool_name", ""),
                        confirmation_token=getattr(final_result, "confirmation_token", "") or "",
                        description=getattr(final_result, "summary", "") or "",
                        arguments=dict(getattr(call, "arguments", {}) or {}),
                    )
                    yield ChatDoneMessage(message_id=msg.message_id)
                    return

                if aborted or final_result is None:
                    yield ChatDoneMessage(message_id=msg.message_id)
                    return

                # 5) Append format_result_for_llm() output built from the result
                # we ALREADY have (no second execution).
                formatted: dict[str, object] | None = None
                try:
                    formatted = tool_manager.format_result_for_llm(call, final_result)
                    # Truncate long content fields safely
                    content_val = formatted.get("content")
                    if isinstance(content_val, str) and len(content_val) > 2000:
                        formatted["content"] = content_val[:2000] + "..."
                except Exception:
                    logger.exception("Failed to format tool result for OpenAI-native history")

                # Always append only well-formed tool messages.
                # OpenAI-compatible providers require tool_call_id.
                if isinstance(formatted, dict) and formatted.get("role") == "tool" and formatted.get("tool_call_id"):
                    history.append(formatted)
                else:
                    logger.warning(
                        "Dropping malformed/orphan tool result message. tool=%s call_id=%s",
                        call.tool_name,
                        getattr(call, "call_id", None),
                    )
                    # Do not append fallback role=tool message; it can corrupt tool sequencing.
                    continue

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
                    session, msg.conversation_id, all_messages,
                    user_id=user_id, save_as_memory=True,
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
    from dash_backend.chat.service import add_message, create_conversation
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

    # Guard: never forward an unavailable/placeholder transcription into the
    # chat/LLM pipeline. The noop provider returns "[voice transcription
    # not available]" when no STT engine is configured. Surface that as a
    # clean voice.stt.error instead of making a meaningless LLM request.
    transcript_clean = (transcript or "").strip()
    if not transcript_clean or "not available" in transcript_clean.lower() or "failed" in transcript_clean.lower():
        logger.warning("STT returned no usable transcript; emitting voice.stt.error")
        yield voice_stt_error(msg.request_id, "Speech-to-text unavailable")
        return

    # Strip wake word prefix if present (e.g. "Hey DASH, what time is it?" -> "what time is it?")
    import re
    # Build patterns from user's custom wake word + defaults
    user_id_str = str(user_id) if user_id else ""
    try:
        from dash_backend.api.routes.remote_control import get_user_wake_word
        custom_phrase = get_user_wake_word(user_id_str)
    except Exception:
        custom_phrase = "Hey DASH"
    
    # Escape the custom phrase for regex and build pattern
    escaped_custom = re.escape(custom_phrase)
    wake_patterns = [
        rf"^{escaped_custom}[,.:;!?\s]+",
        r"^hey\s*dash[,.:;!?\s]+",
        r"^ok\s*dash[,.:;!?\s]+",
        r"^hello\s*dash[,.:;!?\s]+",
        r"^dash[,.:;!?\s]+",
    ]
    for pattern in wake_patterns:
        transcript_clean = re.sub(pattern, "", transcript_clean, flags=re.IGNORECASE).strip()
    
    if not transcript_clean:
        # Just the wake word with no command — acknowledge
        yield VoiceSTTDoneMessage(request_id=msg.request_id, text="Hey! I'm listening.")
        yield ChatTokenMessage(message_id=str(uuid.uuid4()), content="Hey! I'm listening. What can I do for you?")
        return

    # Send STT done message
    yield VoiceSTTDoneMessage(request_id=msg.request_id, text=transcript_clean)

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
    try:
        conversation = await create_conversation(session=session, user_id=user_id)
        await add_message(session=session, conversation_id=conversation.id, role=MessageRole.USER, content=transcript)

        chat_msg = ChatSendMessage(conversation_id=conversation.id, message_id=str(uuid.uuid4()), content=transcript, voice_mode=True)

        # Collect the full assistant response for streaming TTS
        assistant_response_parts = []
        async for event in handle_chat_send(chat_msg, session=session, user_id=user_id):
            yield event
            # Capture chat token content for TTS
            if hasattr(event, 'content') and hasattr(event, 'message_id'):
                assistant_response_parts.append(event.content or "")

        # Streaming TTS: synthesize response sentence by sentence
        full_response = "".join(assistant_response_parts)
        if full_response.strip():
            try:
                from dash_backend.voice import synthesize_text
                import re

                # Split into sentences for streaming
                sentences = re.split(r'(?<=[.!?])\s+', full_response.strip())
                sentences = [s.strip() for s in sentences if s.strip()]

                for i, sentence in enumerate(sentences):
                    try:
                        audio_b64 = await synthesize_text(sentence, user_id=user_id)
                        if audio_b64:
                            yield VoiceTTSDoneMessage(
                                request_id=msg.request_id,
                                audio_base64=audio_b64
                            )
                    except Exception:
                        logger.warning("TTS chunk %d failed, skipping", i)
                        continue

            except Exception:
                logger.exception("Streaming TTS failed")
    except Exception:
        logger.exception("Failed to forward STT to chat pipeline")
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


# ── Phone Integration Handlers ───────────────────────────────────


def _adb_service():
    """Get the global ADB service (imported lazily to avoid cycles)."""
    from dash_backend.phone.adb_service import get_adb_service

    return get_adb_service()


async def handle_phone_state(msg: PhoneStateMessage) -> AsyncIterator[object]:
    """Handle phone state updates: store snapshot and broadcast to clients."""
    logger.info("Phone state received: battery=%s%%, storage=%s%%",
                msg.battery.get("level", 0), msg.storage.get("used_percent", 0))
    try:
        from dash_backend.cache.simple_cache import get_cache

        cache = get_cache()
        cache.set(
            "phone_state_latest",
            {
                "battery": dict(msg.battery),
                "storage": dict(msg.storage),
                "network": dict(getattr(msg, "network", {}) or {}),
                "timestamp": msg.timestamp,
            },
            ttl=3600.0,
        )
    except Exception:
        logger.exception("Failed to store phone state")
    # Broadcast the state so desktop clients can react.
    yield {
        "type": "phone.state",
        "battery": dict(msg.battery),
        "storage": dict(msg.storage),
        "network": dict(getattr(msg, "network", {}) or {}),
        "timestamp": msg.timestamp,
    }
    yield {"type": "phone.state.ack", "timestamp": msg.timestamp}


async def handle_phone_clipboard_get(msg: PhoneClipboardGetMessage) -> AsyncIterator[object]:
    """Handle request to read phone clipboard via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        result = await _adb_service().read_clipboard(serial)
        yield {
            "type": "phone.clipboard.response",
            "text": result.get("text", "") if result.get("ok") else "",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone clipboard get failed")
        yield {"type": "phone.clipboard.response", "text": "", "status": "error", "error": str(exc)}


async def handle_phone_clipboard_set(msg: PhoneClipboardSetMessage) -> AsyncIterator[object]:
    """Handle request to set phone clipboard via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        result = await _adb_service().write_clipboard(msg.text, serial)
        yield {
            "type": "phone.clipboard.set.ack",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone clipboard set failed")
        yield {"type": "phone.clipboard.set.ack", "status": "error", "error": str(exc)}


async def handle_phone_volume_get(msg: PhoneVolumeGetMessage) -> AsyncIterator[object]:
    """Handle request to get phone volume via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        svc = _adb_service()
        result = await svc._adb(
            [*svc._device_prefix(serial), "shell", "media", "volume", "--get", "music"],
        )
        volume = 0
        if result.get("ok"):
            try:
                volume = int(str(result.get("stdout", "")).strip())
            except (TypeError, ValueError):
                volume = 0
        yield {
            "type": "phone.volume.response",
            "volume": volume,
            "is_muted": False,
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone volume get failed")
        yield {"type": "phone.volume.response", "volume": 0, "is_muted": False, "status": "error", "error": str(exc)}


async def handle_phone_volume_set(msg: PhoneVolumeSetMessage) -> AsyncIterator[object]:
    """Handle request to set phone volume via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        svc = _adb_service()
        result = await svc._adb(
            [*svc._device_prefix(serial), "shell", "media", "volume", "--set", str(msg.level), "music"],
        )
        yield {
            "type": "phone.volume.set.ack",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone volume set failed")
        yield {"type": "phone.volume.set.ack", "status": "error", "error": str(exc)}


async def handle_phone_volume_mute(msg: PhoneVolumeMuteMessage) -> AsyncIterator[object]:
    """Handle request to toggle phone mute via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        svc = _adb_service()
        result = await svc._adb(
            [*svc._device_prefix(serial), "shell", "media", "volume", "--mute", "music"],
        )
        yield {
            "type": "phone.volume.mute.ack",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone volume mute failed")
        yield {"type": "phone.volume.mute.ack", "status": "error", "error": str(exc)}


async def handle_phone_flashlight_toggle(msg: PhoneFlashlightToggleMessage) -> AsyncIterator[object]:
    """Handle flashlight toggle request via ADB camera keyevent."""
    serial = getattr(msg, "serial", None)
    try:
        svc = _adb_service()
        result = await svc._adb(
            [*svc._device_prefix(serial), "shell", "input", "keyevent", "KEYCODE_CAMERA"],
        )
        yield {
            "type": "phone.flashlight.toggle.ack",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone flashlight toggle failed")
        yield {"type": "phone.flashlight.toggle.ack", "status": "error", "error": str(exc)}


async def handle_phone_notifications_get(msg: PhoneNotificationsGetMessage) -> AsyncIterator[object]:
    """Handle request to get phone notifications via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        result = await _adb_service().get_notifications(serial)
        yield {
            "type": "phone.notifications.response",
            "notifications": result.get("notifications", []) if result.get("ok") else [],
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone notifications get failed")
        yield {"type": "phone.notifications.response", "notifications": [], "status": "error", "error": str(exc)}


async def handle_phone_notifications_clear(msg: PhoneNotificationsClearMessage) -> AsyncIterator[object]:
    """Handle request to clear phone notifications via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        result = await _adb_service().clear_notifications(serial)
        yield {
            "type": "phone.notifications.clear.ack",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone notifications clear failed")
        yield {"type": "phone.notifications.clear.ack", "status": "error", "error": str(exc)}


async def handle_phone_apps_get(msg: PhoneAppsGetMessage) -> AsyncIterator[object]:
    """Handle request to get installed apps via ADB."""
    serial = getattr(msg, "serial", None)
    package_hint = getattr(msg, "package_hint", "") or ""
    try:
        result = await _adb_service().list_apps(serial, package_hint)
        yield {
            "type": "phone.apps.response",
            "apps": result.get("packages", []) if result.get("ok") else [],
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone apps get failed")
        yield {"type": "phone.apps.response", "apps": [], "status": "error", "error": str(exc)}


async def handle_phone_apps_open(msg: PhoneAppsOpenMessage) -> AsyncIterator[object]:
    """Handle request to open app on phone via ADB."""
    serial = getattr(msg, "serial", None)
    try:
        result = await _adb_service().open_app(msg.package_name, serial)
        yield {
            "type": "phone.apps.open.ack",
            "status": "ok" if result.get("ok") else "error",
        }
    except Exception as exc:
        logger.exception("Phone apps open failed")
        yield {"type": "phone.apps.open.ack", "status": "error", "error": str(exc)}


async def _phone_media_key(keyevent: str, ack_type: str) -> AsyncIterator[object]:
    """Send a media keyevent to the connected phone via ADB."""
    serial = None
    try:
        svc = _adb_service()
        result = await svc._adb(
            [*svc._device_prefix(serial), "shell", "input", "keyevent", keyevent],
        )
        yield {"type": ack_type, "status": "ok" if result.get("ok") else "error"}
    except Exception as exc:
        logger.exception("Phone media key %s failed", keyevent)
        yield {"type": ack_type, "status": "error", "error": str(exc)}


async def handle_phone_media_play(msg: PhoneMediaPlayMessage) -> AsyncIterator[object]:
    """Handle request to play media on phone."""
    logger.info("Phone media play request")
    async for event in _phone_media_key("KEYCODE_MEDIA_PLAY", "phone.media.play.ack"):
        yield event


async def handle_phone_media_pause(msg: PhoneMediaPauseMessage) -> AsyncIterator[object]:
    """Handle request to pause media on phone."""
    logger.info("Phone media pause request")
    async for event in _phone_media_key("KEYCODE_MEDIA_PAUSE", "phone.media.pause.ack"):
        yield event


async def handle_phone_media_next(msg: PhoneMediaNextMessage) -> AsyncIterator[object]:
    """Handle request to skip to next track on phone."""
    logger.info("Phone media next request")
    async for event in _phone_media_key("KEYCODE_MEDIA_NEXT", "phone.media.next.ack"):
        yield event


async def handle_phone_media_previous(msg: PhoneMediaPreviousMessage) -> AsyncIterator[object]:
    """Handle request to go to previous track on phone."""
    logger.info("Phone media previous request")
    async for event in _phone_media_key("KEYCODE_MEDIA_PREVIOUS", "phone.media.previous.ack"):
        yield event


# ── Desktop Control Handlers (from phone) ──────────────────────


async def handle_desktop_mouse_move(msg: DesktopMouseMoveMessage) -> AsyncIterator[object]:
    """Handle mouse move command from phone."""
    logger.info("Desktop mouse move: x=%d, y=%d", msg.x, msg.y)
    try:
        from dash_backend.services.mouse import MouseService
        svc = MouseService()
        result = await svc.move(msg.x, msg.y)
        yield {"type": "desktop.mouse.move.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop mouse move failed")
        yield {"type": "desktop.mouse.move.ack", "status": "error", "error": str(exc)}


async def handle_desktop_mouse_click(msg: DesktopMouseClickMessage) -> AsyncIterator[object]:
    """Handle mouse click command from phone."""
    logger.info("Desktop mouse click: button=%s, x=%s, y=%s", msg.button, msg.x, msg.y)
    try:
        from dash_backend.services.mouse import MouseService
        svc = MouseService()
        if msg.x is not None and msg.y is not None:
            await svc.move(msg.x, msg.y)
        result = await svc.click(button=msg.button)
        yield {"type": "desktop.mouse.click.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop mouse click failed")
        yield {"type": "desktop.mouse.click.ack", "status": "error", "error": str(exc)}


async def handle_desktop_mouse_scroll(msg: DesktopMouseScrollMessage) -> AsyncIterator[object]:
    """Handle mouse scroll command from phone."""
    logger.info("Desktop mouse scroll: clicks=%d", msg.clicks)
    try:
        from dash_backend.services.mouse import MouseService
        svc = MouseService()
        result = await svc.scroll(clicks=msg.clicks)
        yield {"type": "desktop.mouse.scroll.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop mouse scroll failed")
        yield {"type": "desktop.mouse.scroll.ack", "status": "error", "error": str(exc)}


async def handle_desktop_keyboard_type(msg: DesktopKeyboardTypeMessage) -> AsyncIterator[object]:
    """Handle keyboard type command from phone."""
    logger.info("Desktop keyboard type: text length=%d", len(msg.text))
    try:
        from dash_backend.services.keyboard import KeyboardService
        svc = KeyboardService()
        result = await svc.type_text(msg.text)
        yield {"type": "desktop.keyboard.type.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop keyboard type failed")
        yield {"type": "desktop.keyboard.type.ack", "status": "error", "error": str(exc)}


async def handle_desktop_keyboard_press(msg: DesktopKeyboardPressMessage) -> AsyncIterator[object]:
    """Handle keyboard press command from phone."""
    logger.info("Desktop keyboard press: key=%s", msg.key)
    try:
        from dash_backend.services.keyboard import KeyboardService
        svc = KeyboardService()
        result = await svc.press(msg.key)
        yield {"type": "desktop.keyboard.press.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop keyboard press failed")
        yield {"type": "desktop.keyboard.press.ack", "status": "error", "error": str(exc)}


async def handle_desktop_keyboard_hotkey(msg: DesktopKeyboardHotkeyMessage) -> AsyncIterator[object]:
    """Handle keyboard hotkey command from phone."""
    logger.info("Desktop keyboard hotkey: keys=%s", msg.keys)
    try:
        from dash_backend.services.keyboard import KeyboardService
        svc = KeyboardService()
        result = await svc.hotkey(*msg.keys)
        yield {"type": "desktop.keyboard.hotkey.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop keyboard hotkey failed")
        yield {"type": "desktop.keyboard.hotkey.ack", "status": "error", "error": str(exc)}


async def handle_desktop_power_shutdown(msg: DesktopPowerShutdownMessage) -> AsyncIterator[object]:
    """Handle desktop shutdown command from phone."""
    logger.info("Desktop power shutdown: force=%s, timeout=%d", msg.force, msg.timeout)
    try:
        from dash_backend.services.power import PowerService
        svc = PowerService()
        result = await svc.shutdown(force=msg.force, timeout=msg.timeout)
        yield {"type": "desktop.power.shutdown.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop power shutdown failed")
        yield {"type": "desktop.power.shutdown.ack", "status": "error", "error": str(exc)}


async def handle_desktop_power_restart(msg: DesktopPowerRestartMessage) -> AsyncIterator[object]:
    """Handle desktop restart command from phone."""
    logger.info("Desktop power restart: force=%s, timeout=%d", msg.force, msg.timeout)
    try:
        from dash_backend.services.power import PowerService
        svc = PowerService()
        result = await svc.restart(force=msg.force, timeout=msg.timeout)
        yield {"type": "desktop.power.restart.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop power restart failed")
        yield {"type": "desktop.power.restart.ack", "status": "error", "error": str(exc)}


async def handle_desktop_power_lock(msg: DesktopPowerLockMessage) -> AsyncIterator[object]:
    """Handle desktop lock command from phone."""
    logger.info("Desktop power lock")
    try:
        from dash_backend.services.power import PowerService
        svc = PowerService()
        result = await svc.lock()
        yield {"type": "desktop.power.lock.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop power lock failed")
        yield {"type": "desktop.power.lock.ack", "status": "error", "error": str(exc)}


async def handle_desktop_power_sleep(msg: DesktopPowerSleepMessage) -> AsyncIterator[object]:
    """Handle desktop sleep command from phone."""
    logger.info("Desktop power sleep")
    try:
        from dash_backend.services.power import PowerService
        svc = PowerService()
        result = await svc.sleep()
        yield {"type": "desktop.power.sleep.ack", "status": "ok", "details": result}
    except Exception as exc:
        logger.exception("Desktop power sleep failed")
        yield {"type": "desktop.power.sleep.ack", "status": "error", "error": str(exc)}


async def handle_log_stream(msg, session=None, user_id=None):
    """Stream backend logs to the mobile client via WebSocket.
    
    Sends the last N lines on connect, then streams new lines as they appear.
    Client sends {"type": "logs.subscribe", "component": "backend"} to start.
    """
    import asyncio
    import os
    from dash_backend.logging_config import LOG_DIR, COMPONENT_LOGS
    
    component = getattr(msg, "component", "backend") if hasattr(msg, "component") else "backend"
    log_file = COMPONENT_LOGS.get(component, "backend.log")
    log_path = os.path.join(LOG_DIR, log_file)
    
    if not os.path.exists(log_path):
        yield {"type": "logs.error", "error": f"Log file not found: {log_file}"}
        return
    
    # Send last 50 lines
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            recent = lines[-50:] if len(lines) > 50 else lines
            for line in recent:
                yield {"type": "logs.line", "line": line.rstrip(), "component": component}
    except Exception as e:
        yield {"type": "logs.error", "error": str(e)}
        return
    
    yield {"type": "logs.ready", "component": component}
    
    # Tail new lines every 2 seconds
    try:
        while True:
            await asyncio.sleep(2)
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    new_lines = f.readlines()
                    # Send only lines after what we already sent
                    if len(new_lines) > len(lines):
                        for line in new_lines[len(lines):]:
                            yield {"type": "logs.line", "line": line.rstrip(), "component": component}
                        lines = new_lines
            except Exception:
                pass
    except asyncio.CancelledError:
        pass
