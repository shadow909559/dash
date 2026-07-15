from __future__ import annotations

from typing import AsyncIterator

from dash_backend.api.websocket.protocol import (
    AgentDoneMessage,
    AgentErrorMessage,
    AgentRunMessage,
    AgentStepMessage,
    ChatDoneMessage,
    ChatErrorMessage,
    ChatSendMessage,
    ChatTokenMessage,
    VoiceSTTDoneMessage,
    VoiceSTTErrorMessage,
    VoiceSTTMessage,
    VoiceTTSDoneMessage,
    VoiceTTSErrorMessage,
    VoiceTTSMessage,
)
from dash_backend.llm.service import build_chat_messages, stream_chat_response
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


async def handle_chat_send(msg: ChatSendMessage) -> AsyncIterator[object]:
    """Stream a real AI response from the configured LLM provider."""
    DASH_SYSTEM_PROMPT = (
        "You are DASH, a helpful, capable personal AI assistant. "
        "You are concise but friendly. Answer questions directly and accurately. "
        "When you don't know something, say so. "
        "You can help with coding, writing, analysis, and general knowledge."
    )

    messages = build_chat_messages(
        system_prompt=DASH_SYSTEM_PROMPT,
        user_message=msg.content,
    )

    has_yielded = False
    try:
        async for token in stream_chat_response(messages):
            yield ChatTokenMessage(message_id=msg.message_id, content=token)
            has_yielded = True
    except Exception as exc:
        logger.exception("LLM streaming failed for message %s", msg.message_id)
        yield ChatTokenMessage(
            message_id=msg.message_id,
            content=f"*Sorry, an error occurred while generating a response: {exc}*",
        )
        yield ChatDoneMessage(message_id=msg.message_id)
        return

    if not has_yielded:
        yield ChatTokenMessage(
            message_id=msg.message_id,
            content="I'm not sure how to respond to that yet. Please check your AI provider configuration.",
        )

    yield ChatDoneMessage(message_id=msg.message_id)


async def handle_agent_run(msg: AgentRunMessage) -> AsyncIterator[object]:
    # MVP: single-step agent.
    yield AgentStepMessage(
        request_id=msg.request_id,
        step_index=0,
        output={"echo": msg.input},
    )
    yield AgentDoneMessage(request_id=msg.request_id, output={"result": msg.input})


async def handle_voice_stt(msg: VoiceSTTMessage) -> AsyncIterator[object]:
    # MVP placeholder: no real STT.
    yield VoiceSTTDoneMessage(request_id=msg.request_id, text="[stt-not-implemented]")


async def handle_voice_tts(msg: VoiceTTSMessage) -> AsyncIterator[object]:
    # MVP placeholder: no real TTS.
    yield VoiceTTSDoneMessage(request_id=msg.request_id, audio_base64="")


async def safe_stream(stream: AsyncIterator[object], *, on_error) -> AsyncIterator[object]:
    try:
        async for item in stream:
            yield item
    except Exception as exc:  # pragma: no cover
        yield on_error(str(exc))


def chat_error(message_id: str | None, error: str) -> ChatErrorMessage:
    return ChatErrorMessage(message_id=message_id, error=error)


def agent_error(request_id: str | None, error: str) -> AgentErrorMessage:
    return AgentErrorMessage(request_id=request_id, error=error)


def voice_stt_error(request_id: str, error: str) -> VoiceSTTErrorMessage:
    return VoiceSTTErrorMessage(request_id=request_id, error=error)


def voice_tts_error(request_id: str, error: str) -> VoiceTTSErrorMessage:
    return VoiceTTSErrorMessage(request_id=request_id, error=error)

