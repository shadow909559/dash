"""WebSocket endpoints for real-time communication."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time DASH websocket."""

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

    async def send_json(data: object):
        await websocket.send_json(data)

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

                except Exception as exc:

                    await send_json(
                        ChatErrorMessage(
                            type="chat.error",
                            message_id=None,
                            error=f"Auth failed: {exc}",
                        ).model_dump()
                    )

                continue


            # -------------------------
            # PING
            # -------------------------

            if msg.type == "ping":

                await websocket.send_json(
                    {
                        "type": "pong"
                    }
                )

                continue


            if msg.type == "hello":
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

                await send_json(
                    ChatErrorMessage(
                        type="chat.error",
                        message_id=None,
                        error=f"Unsupported message: {msg.type}",
                    ).model_dump()
                )


    except WebSocketDisconnect:

        logger.info(
            "WebSocket disconnected"
        )


    except Exception:

        logger.exception(
            "WebSocket error"
        )

        await websocket.close(
            code=1011
        )