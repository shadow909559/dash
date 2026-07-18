"""WebSocket endpoints for real-time communication."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time DASH websocket with keepalive and streaming support."""

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
        VoiceSTTMessage,
        VoiceTTSMessage,
        parse_client_message,
    )

    from dash_backend.auth.security import decode_access_token

    await websocket.accept()
    logger.info("WebSocket connected")

    user_id: str | None = None
    disconnected = False

    async def send_json(data: object):
        """Safely send JSON, ignoring errors if disconnected."""
        if disconnected:
            return
        try:
            await websocket.send_json(data)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    async def keepalive_loop():
        """Send periodic pong messages to keep proxies from closing the connection."""
        nonlocal disconnected
        while not disconnected:
            await asyncio.sleep(30)
            if disconnected:
                break
            try:
                await websocket.send_json({"type": "pong"})
            except (WebSocketDisconnect, Exception):
                break

    keepalive_task = asyncio.create_task(keepalive_loop())

    try:
        while True:
            raw_text = await websocket.receive_text()

            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error",
                        message_id=None,
                        error="Invalid JSON",
                    ).model_dump()
                )
                continue

            try:
                msg = parse_client_message(raw)
            except Exception as exc:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error",
                        message_id=None,
                        error=str(exc),
                    ).model_dump()
                )
                continue

            # AUTH
            if msg.type == "auth":
                auth_msg = AuthMessage.model_validate(raw)

                try:
                    payload = decode_access_token(auth_msg.access_token)
                    user_id = payload["sub"]
                    logger.info("Authenticated user: %s", user_id)
                except Exception as exc:
                    logger.warning("Auth failed: %s", exc)
                    await send_json(
                        ChatErrorMessage(
                            type="chat.error",
                            message_id=None,
                            error=f"Auth failed: {exc}",
                        ).model_dump()
                    )

                continue

            # PING / HEARTBEAT
            if msg.type in ("ping", "heartbeat"):
                await websocket.send_json({"type": "pong"})
                continue

            if msg.type == "hello":
                logger.info("Client hello received")
                continue

            if user_id is None:
                await send_json(
                    ChatErrorMessage(
                        type="chat.error",
                        message_id=None,
                        error="Not authenticated",
                    ).model_dump()
                )
                continue

            # CHAT
            if msg.type == "chat.send":
                chat_msg = ChatSendMessage.model_validate(raw)

                from dash_backend.chat.service import add_message, create_conversation, get_conversation

                from dash_backend.db.session import AsyncSessionLocal
                from dash_backend.db.models.message import MessageRole

                async with AsyncSessionLocal() as session:
                    conversation = None
                    if chat_msg.conversation_id:
                        conversation = await get_conversation(
                            session, chat_msg.conversation_id
                        )

                    if conversation is None:
                        conversation = await create_conversation(
                            session=session,
                            user_id=user_id,
                        )

                    # Persist the user message (assistant message is persisted by the handler)
                    await add_message(
                        session=session,
                        conversation_id=conversation.id,
                        role=MessageRole.USER,
                        content=chat_msg.content,
                    )

                    async for event in handle_chat_send(
                        chat_msg,
                        session=session,
                        user_id=user_id,
                    ):
                        await send_json(event.model_dump())

                    logger.info("Completed response for user %s", user_id)

            # VOICE STT
            elif msg.type == "voice.stt":
                stt_msg = VoiceSTTMessage.model_validate(raw)
                from dash_backend.db.session import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    async for event in handle_voice_stt(stt_msg, session=session, user_id=user_id):
                        await send_json(event.model_dump())

            # VOICE TTS
            elif msg.type == "voice.tts":
                tts_msg = VoiceTTSMessage.model_validate(raw)
                from dash_backend.db.session import AsyncSessionLocal
                async with AsyncSessionLocal() as session:
                    async for event in handle_voice_tts(tts_msg, session=session, user_id=user_id):
                        await send_json(event.model_dump())

            # AGENT
            elif msg.type == "agent.run":
                async for event in handle_agent_run(msg):
                    await send_json(event.model_dump())

            else:
                logger.debug("Unsupported message type: %s", msg.type)
                await send_json(
                    ChatErrorMessage(
                        type="chat.error",
                        message_id=None,
                        error=f"Unsupported message: {msg.type}",
                    ).model_dump()
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected (user: %s)", user_id or "unauthenticated")

    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)

    finally:
        disconnected = True
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass

