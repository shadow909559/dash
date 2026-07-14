from __future__ import annotations

import asyncio
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


async def token_stream_for_text(text: str) -> AsyncIterator[str]:
    # MVP: emit word-by-word tokens to mimic streaming.
    words = text.split()
    if not words:
        return
    for w in words:
        yield w + " "
        await asyncio.sleep(0.01)


async def handle_chat_send(msg: ChatSendMessage) -> AsyncIterator[object]:
    # MVP: streaming "assistant" response is just the input uppercased.
    async for token in token_stream_for_text(msg.content.upper()):
        yield ChatTokenMessage(message_id=msg.message_id, content=token)
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

