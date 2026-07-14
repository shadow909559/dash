"""WebSocket endpoints for real-time communication."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Rich websocket endpoint.

    Protocol v1 (JSON messages):
    - client -> server: hello, auth, chat.send, voice.stt, voice.tts, agent.run
    - server -> client: chat.token (stream), chat.done, chat.error, etc.

    MVP streaming is implemented with a small async generator in
    `dash_backend.api.websocket.handlers`.
    """

    from dash_backend.api.websocket.handlers import (
        handle_agent_run,
        handle_chat_send,
        handle_voice_stt,
        handle_voice_tts,
    )
    from dash_backend.api.websocket.protocol import (
        AuthMessage,
        ChatErrorMessage,
        ChatSendMessage,
        parse_client_message,
    )
    from dash_backend.auth.security import decode_access_token

    await websocket.accept()

    user_id: str | None = None

    async def send_json(obj: object) -> None:
        await websocket.send_json(obj)

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error", message_id=None, error="Invalid JSON"
                    ).model_dump()
                )
                continue

            try:
                msg = parse_client_message(raw)
            except Exception as exc:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error", message_id=None, error=str(exc)
                    ).model_dump()
                )
                continue

            # Auth flow
            if msg.type == "auth":
                auth_msg = AuthMessage.model_validate(raw)
                try:
                    payload = decode_access_token(auth_msg.access_token)
                except Exception as exc:
                    await send_json(
                        ChatErrorMessage(
                            type="chat.error",
                            message_id=None,
                            error=f"Auth failed: {exc}",
                        ).model_dump()
                    )
                    continue

                user_id = payload["sub"]
                continue

            if msg.type == "hello" or msg.type == "ping":
                if msg.type == "ping":
                    await websocket.send_json({"type": "pong"})
                continue

            if user_id is None:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error", message_id=None, error="Not authenticated"
                    ).model_dump()
                )
                continue

            # Chat
            if msg.type == "chat.send":
                chat_msg = ChatSendMessage.model_validate(raw)
                async for event in handle_chat_send(chat_msg):
                    await send_json(event.model_dump())

            # Voice
            elif msg.type == "voice.stt":
                async for event in handle_voice_stt(msg):  # type: ignore[arg-type]
                    await send_json(event.model_dump())

            elif msg.type == "voice.tts":
                async for event in handle_voice_tts(msg):  # type: ignore[arg-type]
                    await send_json(event.model_dump())

            # Agent
            elif msg.type == "agent.run":
                async for event in handle_agent_run(msg):  # type: ignore[arg-type]
                    await send_json(event.model_dump())

            else:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error",
                        message_id=None,
                        error=f"Unsupported message: {msg.type}",
                    ).model_dump()
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception:
        logger.exception("WebSocket error")
        await websocket.close(code=1011)

