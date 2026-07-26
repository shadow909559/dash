"""WebSocket endpoints for real-time communication with sync support."""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.api.websocket.handlers import (
    handle_agent_run,
    handle_chat_send,
    handle_voice_stt,
    handle_voice_tts,
)
from dash_backend.api.websocket.protocol import (
    ChatSendMessage,
    VoiceSTTMessage,
    VoiceTTSMessage,
    parse_client_message,
)
from dash_backend.auth.security import decode_access_token
from dash_backend.db.session import AsyncSessionLocal
from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time DASH websocket with keepalive, chat, voice, and agent support."""

    await websocket.accept()
    logger.info("WebSocket connected")

    user_id: str | None = None
    client_id: str | None = None
    disconnected = False

    async def send_json(data: object) -> None:
        if disconnected:
            return
        try:
            await websocket.send_json(data)
        except (WebSocketDisconnect, Exception):
            pass

    async def keepalive_loop() -> None:
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
                await send_json({"type": "chat.error", "message_id": None, "error": "Invalid JSON"})
                continue

            if not isinstance(raw, dict):
                await send_json({"type": "chat.error", "message_id": None, "error": "Expected JSON object"})
                continue

            msg_type = raw.get("type")

            # Authentication
            if msg_type == "auth":
                token = raw.get("access_token", "")
                payload = decode_access_token(token)
                if payload is None:
                    await send_json({"type": "chat.error", "message_id": None, "error": "Invalid token"})
                    await websocket.close(code=4001)
                    return
                user_id = payload.get("sub")
                client_id = raw.get("client_id", str(uuid.uuid4()))
                logger.info("WebSocket authenticated: user=%s", user_id)

                try:
                    from dash_backend.sync.service import get_sync_service
                    sync_service = get_sync_service()
                    await sync_service.register_session(
                        session_id=str(uuid.uuid4()),
                        client_id=client_id,
                        client_type="desktop",
                        user_id=user_id,
                    )
                except Exception:
                    logger.exception("Failed to register sync session")

                await send_json({"type": "session.info", "session_id": client_id, "client_id": client_id})
                continue

            # All other messages require authentication
            if not user_id:
                await send_json({"type": "chat.error", "message_id": None, "error": "Not authenticated"})
                continue

            # Parse typed message
            try:
                msg = parse_client_message(raw)
            except ValueError as exc:
                await send_json({"type": "chat.error", "message_id": None, "error": str(exc)})
                continue

            # Chat send - process user message and stream AI response
            if msg_type == "chat.send":
                chat_msg = msg
                assistant_content = ""

                from dash_backend.chat.service import add_message, create_conversation
                from dash_backend.db.models.message import MessageRole

                # ALWAYS persist user message for both new and existing conversations
                async with AsyncSessionLocal() as session:
                    if not chat_msg.conversation_id:
                        conv = await create_conversation(session, user_id)
                        chat_msg.conversation_id = str(conv.id)
                    await add_message(session, chat_msg.conversation_id, MessageRole.USER, chat_msg.content)

                async with AsyncSessionLocal() as session:
                    async for event in handle_chat_send(chat_msg, session=session, user_id=user_id):
                        if event.type == "chat.token":
                            assistant_content += event.content
                        if event.type == "chat.done":
                            event.conversation_id = chat_msg.conversation_id
                            # Save the complete assistant message to DB after streaming finishes
                            if assistant_content:
                                try:
                                    async with AsyncSessionLocal() as save_session:
                                        await add_message(
                                            save_session,
                                            chat_msg.conversation_id,
                                            MessageRole.ASSISTANT,
                                            assistant_content,
                                        )
                                except Exception as e:
                                    logger.exception("Failed to save assistant message: %s", e)
                        await send_json(event.model_dump())

                    logger.info("Completed chat response for user %s", user_id)

            # Voice STT
            elif msg_type == "voice.stt":
                stt_msg = msg
                async with AsyncSessionLocal() as session:
                    async for event in handle_voice_stt(stt_msg, session=session, user_id=user_id):
                        await send_json(event.model_dump())

            # Voice TTS
            elif msg_type == "voice.tts":
                tts_msg = msg
                async with AsyncSessionLocal() as session:
                    async for event in handle_voice_tts(tts_msg, session=session, user_id=user_id):
                        await send_json(event.model_dump())

            # Agent
            elif msg_type == "agent.run":
                async for event in handle_agent_run(msg):
                    await send_json(event.model_dump())

            else:
                logger.debug("Unsupported message type: %s", msg_type)
                await send_json({"type": "chat.error", "message_id": None, "error": f"Unsupported: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected (user: %s)", user_id or "unauthenticated")
        if client_id:
            try:
                from dash_backend.sync.service import get_sync_service
                sync_service = get_sync_service()
                await sync_service.unregister_session(client_id)
            except Exception:
                pass
    except Exception as exc:
        logger.exception("WebSocket error: %s", exc)
    finally:
        disconnected = True
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass
