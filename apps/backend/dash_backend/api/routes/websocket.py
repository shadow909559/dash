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
        """Send periodic pongs? No, server just waits for client pings.
        
        Actually, the server doesn't need to send pings - FastAPI/uvicorn
        handles the WebSocket. We just need to be responsive to client
        heartbeats. If the client doesn't send anything for a long time,
        the OS TCP stack keeps the connection alive.
        
        But to prevent proxies from closing idle connections,
        we send a small "keepalive" message occasionally.
        """
        nonlocal disconnected
        while not disconnected:
            await asyncio.sleep(30)
            if disconnected:
                break
            try:
                # Send a simple pong-like keepalive
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


            # -------------------------
            # AUTH
            # -------------------------

            if msg.type == "auth":

                auth_msg = AuthMessage.model_validate(raw)

                try:
                    payload = decode_access_token(
                        auth_msg.access_token
                    )

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


            # -------------------------
            # PING / HEARTBEAT
            # -------------------------

            if msg.type in ("ping", "heartbeat"):

                await websocket.send_json(
                    {
                        "type": "pong"
                    }
                )

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



            # -------------------------
            # CHAT
            # -------------------------

            if msg.type == "chat.send":

                chat_msg = ChatSendMessage.model_validate(raw)

                assistant_text = ""
                logger.info("Received chat.send from user %s", user_id)

                from dash_backend.db.session import AsyncSessionLocal

                from dash_backend.chat.service import (
                    get_or_create_conversation,
                    save_user_message,
                    save_assistant_message,
                )


                async with AsyncSessionLocal() as session:

                    conversation = await get_or_create_conversation(
                        session=session,
                        user_id=user_id,
                        conversation_id=chat_msg.conversation_id,
                    )


                    await save_user_message(
                        session=session,
                        conversation_id=str(conversation.id),
                        content=chat_msg.content,
                    )


                    async for event in handle_chat_send(chat_msg):

                        if event.type == "chat.token":

                            assistant_text += event.content


                        await send_json(
                            event.model_dump()
                        )


                    await save_assistant_message(
                        session=session,
                        conversation_id=str(conversation.id),
                        content=assistant_text,
                    )

                    logger.info(
                        "Completed response for user %s (%d chars)",
                        user_id,
                        len(assistant_text),
                    )



            # -------------------------
            # VOICE STT
            # -------------------------

            elif msg.type == "voice.stt":

                async for event in handle_voice_stt(msg):

                    await send_json(
                        event.model_dump()
                    )



            # -------------------------
            # VOICE TTS
            # -------------------------

            elif msg.type == "voice.tts":

                async for event in handle_voice_tts(msg):

                    await send_json(
                        event.model_dump()
                    )



            # -------------------------
            # AGENT
            # -------------------------

            elif msg.type == "agent.run":

                async for event in handle_agent_run(msg):

                    await send_json(
                        event.model_dump()
                    )



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
