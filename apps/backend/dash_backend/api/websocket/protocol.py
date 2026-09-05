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
    "chat.status",
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
    # Phone integration
    "phone.state",
    "phone.clipboard.get",
    "phone.clipboard.set",
    "phone.volume.get",
    "phone.volume.set",
    "phone.volume.mute",
    "phone.flashlight.toggle",
    "phone.notifications.get",
    "phone.notifications.clear",
    "phone.apps.get",
    "phone.apps.open",
    "phone.media.play",
    "phone.media.pause",
    "phone.media.next",
    "phone.media.previous",
    # Desktop control from phone
    "desktop.mouse.move",
    "desktop.mouse.click",
    "desktop.mouse.scroll",
    "desktop.keyboard.type",
    "desktop.keyboard.press",
    "desktop.keyboard.hotkey",
    "desktop.power.shutdown",
    "desktop.power.restart",
    "desktop.power.lock",
    "desktop.power.sleep",
    # AI Provider status
    "ai.provider.status",
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
    # Optional agent selection (agent id as UUID string). If provided, the agent's
    # system_prompt will be injected into the LLM system prompt for this request.
    agent_id: str | None = None
    # Agent mode: general, coder, planner, research, executor
    agent_mode: str = "general"
    # Voice mode: when True, LLM is instructed to reply with short, spoken-friendly text
    voice_mode: bool = False


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
    conversation_id: str | None = None


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
# Phone Integration Messages
# -------------------------


class PhoneStateMessage(WSBaseMessage):
    type: Literal["phone.state"] = "phone.state"

    battery: dict[str, Any] = Field(default_factory=dict)
    storage: dict[str, Any] = Field(default_factory=dict)
    network: dict[str, Any] = Field(default_factory=dict)
    clipboard: str = ""
    volume: dict[str, Any] = Field(default_factory=dict)
    flashlight: bool = False
    notifications_enabled: bool = True
    timestamp: float = 0.0


class PhoneClipboardGetMessage(WSBaseMessage):
    type: Literal["phone.clipboard.get"] = "phone.clipboard.get"


class PhoneClipboardSetMessage(WSBaseMessage):
    type: Literal["phone.clipboard.set"] = "phone.clipboard.set"

    text: str = ""


class PhoneVolumeGetMessage(WSBaseMessage):
    type: Literal["phone.volume.get"] = "phone.volume.get"


class PhoneVolumeSetMessage(WSBaseMessage):
    type: Literal["phone.volume.set"] = "phone.volume.set"

    level: int = 0


class PhoneVolumeMuteMessage(WSBaseMessage):
    type: Literal["phone.volume.mute"] = "phone.volume.mute"


class PhoneFlashlightToggleMessage(WSBaseMessage):
    type: Literal["phone.flashlight.toggle"] = "phone.flashlight.toggle"

    enabled: bool = False


class PhoneNotificationsGetMessage(WSBaseMessage):
    type: Literal["phone.notifications.get"] = "phone.notifications.get"


class PhoneNotificationsClearMessage(WSBaseMessage):
    type: Literal["phone.notifications.clear"] = "phone.notifications.clear"


class PhoneAppsGetMessage(WSBaseMessage):
    type: Literal["phone.apps.get"] = "phone.apps.get"


class PhoneAppsOpenMessage(WSBaseMessage):
    type: Literal["phone.apps.open"] = "phone.apps.open"

    package_name: str = ""


class PhoneMediaPlayMessage(WSBaseMessage):
    type: Literal["phone.media.play"] = "phone.media.play"


class PhoneMediaPauseMessage(WSBaseMessage):
    type: Literal["phone.media.pause"] = "phone.media.pause"


class PhoneMediaNextMessage(WSBaseMessage):
    type: Literal["phone.media.next"] = "phone.media.next"


class PhoneMediaPreviousMessage(WSBaseMessage):
    type: Literal["phone.media.previous"] = "phone.media.previous"


# -------------------------
# Desktop Control Messages (from phone)
# -------------------------


class DesktopMouseMoveMessage(WSBaseMessage):
    type: Literal["desktop.mouse.move"] = "desktop.mouse.move"

    x: int = 0
    y: int = 0


class DesktopMouseClickMessage(WSBaseMessage):
    type: Literal["desktop.mouse.click"] = "desktop.mouse.click"

    button: str = "left"
    x: int | None = None
    y: int | None = None


class DesktopMouseScrollMessage(WSBaseMessage):
    type: Literal["desktop.mouse.scroll"] = "desktop.mouse.scroll"

    clicks: int = 1


class DesktopKeyboardTypeMessage(WSBaseMessage):
    type: Literal["desktop.keyboard.type"] = "desktop.keyboard.type"

    text: str = ""


class DesktopKeyboardPressMessage(WSBaseMessage):
    type: Literal["desktop.keyboard.press"] = "desktop.keyboard.press"

    key: str = ""


class DesktopKeyboardHotkeyMessage(WSBaseMessage):
    type: Literal["desktop.keyboard.hotkey"] = "desktop.keyboard.hotkey"

    keys: list[str] = Field(default_factory=list)


class DesktopPowerShutdownMessage(WSBaseMessage):
    type: Literal["desktop.power.shutdown"] = "desktop.power.shutdown"

    force: bool = False
    timeout: int = 30


class DesktopPowerRestartMessage(WSBaseMessage):
    type: Literal["desktop.power.restart"] = "desktop.power.restart"

    force: bool = False
    timeout: int = 30


class DesktopPowerLockMessage(WSBaseMessage):
    type: Literal["desktop.power.lock"] = "desktop.power.lock"


class DesktopPowerSleepMessage(WSBaseMessage):
    type: Literal["desktop.power.sleep"] = "desktop.power.sleep"


# -------------------------
# AI Provider Status
# -------------------------


class AIProviderStatusMessage(WSBaseMessage):
    type: Literal["ai.provider.status"] = "ai.provider.status"

    status: str  # checking, starting, ready, model_missing, unavailable, error
    provider: str
    configured_model: str | None = None
    model_available: bool = False
    installed_models: list[str] = Field(default_factory=list)
    error: str | None = None
    latency_ms: float | None = None
    message: str  # User-friendly message


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

    # Phone integration
    if msg_type == "phone.state":
        return PhoneStateMessage.model_validate(raw)
    if msg_type == "phone.clipboard.get":
        return PhoneClipboardGetMessage.model_validate(raw)
    if msg_type == "phone.clipboard.set":
        return PhoneClipboardSetMessage.model_validate(raw)
    if msg_type == "phone.volume.get":
        return PhoneVolumeGetMessage.model_validate(raw)
    if msg_type == "phone.volume.set":
        return PhoneVolumeSetMessage.model_validate(raw)
    if msg_type == "phone.volume.mute":
        return PhoneVolumeMuteMessage.model_validate(raw)
    if msg_type == "phone.flashlight.toggle":
        return PhoneFlashlightToggleMessage.model_validate(raw)
    if msg_type == "phone.notifications.get":
        return PhoneNotificationsGetMessage.model_validate(raw)
    if msg_type == "phone.notifications.clear":
        return PhoneNotificationsClearMessage.model_validate(raw)
    if msg_type == "phone.apps.get":
        return PhoneAppsGetMessage.model_validate(raw)
    if msg_type == "phone.apps.open":
        return PhoneAppsOpenMessage.model_validate(raw)
    if msg_type == "phone.media.play":
        return PhoneMediaPlayMessage.model_validate(raw)
    if msg_type == "phone.media.pause":
        return PhoneMediaPauseMessage.model_validate(raw)
    if msg_type == "phone.media.next":
        return PhoneMediaNextMessage.model_validate(raw)
    if msg_type == "phone.media.previous":
        return PhoneMediaPreviousMessage.model_validate(raw)

    # Desktop control from phone
    if msg_type == "desktop.mouse.move":
        return DesktopMouseMoveMessage.model_validate(raw)
    if msg_type == "desktop.mouse.click":
        return DesktopMouseClickMessage.model_validate(raw)
    if msg_type == "desktop.mouse.scroll":
        return DesktopMouseScrollMessage.model_validate(raw)
    if msg_type == "desktop.keyboard.type":
        return DesktopKeyboardTypeMessage.model_validate(raw)
    if msg_type == "desktop.keyboard.press":
        return DesktopKeyboardPressMessage.model_validate(raw)
    if msg_type == "desktop.keyboard.hotkey":
        return DesktopKeyboardHotkeyMessage.model_validate(raw)
    if msg_type == "desktop.power.shutdown":
        return DesktopPowerShutdownMessage.model_validate(raw)
    if msg_type == "desktop.power.restart":
        return DesktopPowerRestartMessage.model_validate(raw)
    if msg_type == "desktop.power.lock":
        return DesktopPowerLockMessage.model_validate(raw)
    if msg_type == "desktop.power.sleep":
        return DesktopPowerSleepMessage.model_validate(raw)

    raise ValueError(f"Unsupported message type: {msg_type}")

