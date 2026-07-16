from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


WSMessageType = Literal[
    # Lifecycle / auth
    "hello",
    "auth",
    "ping",
    "pong",
    # Chat
    "chat.send",
    "chat.token",
    "chat.done",
    "chat.error",
    # Voice (MVP placeholders)
    "voice.stt",
    "voice.stt.done",
    "voice.stt.error",
    "voice.tts",
    "voice.tts.done",
    "voice.tts.error",
    # Agent (MVP placeholder)
    "agent.run",
    "agent.step",
    "agent.done",
    "agent.error",
    # Tool calling
    "tool.started",
    "tool.progress",
    "tool.finished",
    "tool.error",
    "tool.confirmation_required",
    "tool.confirmed",
    "tool.rejected",
    "tool.list",
    "tool.list.response",
]


class WSBaseMessage(BaseModel):
    type: WSMessageType


# -------------------------
# Client -> Server
# -------------------------


class HelloMessage(WSBaseMessage):
    type: Literal["hello"] = "hello"
    client: str = Field(default="dash-mobile")
    client_version: str | None = None


class AuthMessage(WSBaseMessage):
    type: Literal["auth"] = "auth"
    access_token: str


class PingMessage(WSBaseMessage):
    type: Literal["ping"] = "ping"


class ChatSendMessage(WSBaseMessage):
    type: Literal["chat.send"] = "chat.send"

    conversation_id: str | None = None
    message_id: str
    content: str


class VoiceSTTMessage(WSBaseMessage):
    type: Literal["voice.stt"] = "voice.stt"

    # MVP: we accept base64 audio or a provider-specific token.
    request_id: str
    audio_base64: str


class VoiceTTSMessage(WSBaseMessage):
    type: Literal["voice.tts"] = "voice.tts"

    request_id: str
    text: str


class AgentRunMessage(WSBaseMessage):
    type: Literal["agent.run"] = "agent.run"

    request_id: str
    input: str


class ToolConfirmedMessage(WSBaseMessage):
    type: Literal["tool.confirmed"] = "tool.confirmed"
    confirmation_token: str


class ToolRejectedMessage(WSBaseMessage):
    type: Literal["tool.rejected"] = "tool.rejected"
    confirmation_token: str


# -------------------------
# Server -> Client
# -------------------------


class PongMessage(WSBaseMessage):
    type: Literal["pong"] = "pong"


class ChatTokenMessage(WSBaseMessage):
    type: Literal["chat.token"] = "chat.token"

    message_id: str
    content: str


class ChatDoneMessage(WSBaseMessage):
    type: Literal["chat.done"] = "chat.done"

    message_id: str


class ChatErrorMessage(WSBaseMessage):
    type: Literal["chat.error"] = "chat.error"

    message_id: str | None = None
    error: str


class VoiceSTTDoneMessage(WSBaseMessage):
    type: Literal["voice.stt.done"] = "voice.stt.done"

    request_id: str
    text: str


class VoiceSTTErrorMessage(WSBaseMessage):
    type: Literal["voice.stt.error"] = "voice.stt.error"

    request_id: str
    error: str


class VoiceTTSDoneMessage(WSBaseMessage):
    type: Literal["voice.tts.done"] = "voice.tts.done"

    request_id: str
    audio_base64: str


class VoiceTTSErrorMessage(WSBaseMessage):
    type: Literal["voice.tts.error"] = "voice.tts.error"

    request_id: str
    error: str


class AgentStepMessage(WSBaseMessage):
    type: Literal["agent.step"] = "agent.step"

    request_id: str
    step_index: int
    output: dict[str, Any] = Field(default_factory=dict)


class AgentDoneMessage(WSBaseMessage):
    type: Literal["agent.done"] = "agent.done"

    request_id: str
    output: dict[str, Any] = Field(default_factory=dict)


class AgentErrorMessage(WSBaseMessage):
    type: Literal["agent.error"] = "agent.error"

    request_id: str | None = None
    error: str


# -------------------------
# Tool Messages
# -------------------------


class ToolStartedMessage(WSBaseMessage):
    type: Literal["tool.started"] = "tool.started"

    tool_name: str
    tool_call: dict[str, Any] = Field(default_factory=dict)
    arguments: dict[str, Any] = Field(default_factory=dict)
    started_at: str = ""


class ToolProgressMessage(WSBaseMessage):
    type: Literal["tool.progress"] = "tool.progress"

    tool_name: str
    progress: float = 0.0
    message: str = ""


class ToolFinishedMessage(WSBaseMessage):
    type: Literal["tool.finished"] = "tool.finished"

    tool_name: str
    status: str = "success"
    output: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    duration_ms: float = 0.0


class ToolErrorMessage(WSBaseMessage):
    type: Literal["tool.error"] = "tool.error"

    tool_name: str
    error: str = ""
    status: str = "error"


class ToolConfirmationRequiredMessage(WSBaseMessage):
    type: Literal["tool.confirmation_required"] = "tool.confirmation_required"

    tool_name: str
    confirmation_token: str
    description: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)


# Note: ToolConfirmedMessage / ToolRejectedMessage are client->server models.
# They are defined above.


class ToolListMessage(WSBaseMessage):
    type: Literal["tool.list"] = "tool.list"


class ToolListResponseMessage(WSBaseMessage):
    type: Literal["tool.list.response"] = "tool.list.response"

    tools: list[dict[str, Any]] = Field(default_factory=list)


# -------------------------
# Helpers
# -------------------------


def parse_client_message(raw: Any) -> WSBaseMessage:
    """Parse and validate an inbound websocket JSON payload."""

    if not isinstance(raw, dict):
        raise ValueError("Message must be a JSON object")

    msg_type = raw.get("type")
    if not isinstance(msg_type, str):
        raise ValueError("Missing message type")

    # Auth / hello / ping / heartbeat
    if msg_type == "hello":
        return HelloMessage.model_validate(raw)
    if msg_type == "auth":
        return AuthMessage.model_validate(raw)
    if msg_type in ("ping", "heartbeat"):
        return PingMessage()

    # Chat
    if msg_type == "chat.send":
        return ChatSendMessage.model_validate(raw)

    # Voice
    if msg_type == "voice.stt":
        return VoiceSTTMessage.model_validate(raw)
    if msg_type == "voice.tts":
        return VoiceTTSMessage.model_validate(raw)

    # Agent
    if msg_type == "agent.run":
        return AgentRunMessage.model_validate(raw)

    # Tool confirmation
    if msg_type == "tool.confirmed":
        return ToolConfirmedMessage.model_validate(raw)
    if msg_type == "tool.rejected":
        return ToolRejectedMessage.model_validate(raw)

    raise ValueError(f"Unsupported message type: {msg_type}")

