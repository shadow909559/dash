"""WebSocket endpoints for real-time communication with sync support."""

import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time DASH websocket with keepalive, sync, and streaming support.

    Supports:
    - Session recovery via sync.register
    - Heartbeat tracking
    - Offline message queue delivery
    - Message deduplication
    - Chat, voice, and agent streaming
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
        VoiceSTTMessage,
        VoiceTTSMessage,
        parse_client_message,
    )

    from dash_backend.auth.security import decode_access_token
    from dash_backend.sync.service import get_sync_service

    await websocket.accept()
    logger.info("WebSocket connected")

    user_id: str | None = None
    client_id: str | None = None
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

                    # Register sync session for recovery
                    sync_service = get_sync_service()
                    session_id = str(uuid.uuid4())
                    client_id = f"ws_{user_id}_{session_id[:8]}"
                    session_result = await sync_service.register_session(
                        session_id=session_id,
                        client_id=client_id,
                        client_type="mobile",
                        user_id=user_id,
                    )

                    # Send session info to client
                    await send_json({
                        "type": "session.info",
                        "session_id": session_id,
                        "client_id": client_id,
                        "recovery_count": session_result.get("recovery_count", 0),
                        "requires_full_sync": session_result.get("requires_full_sync", False),
                    })

                    # Deliver any queued offline messages
                    queued = session_result.get("queued_messages", [])
                    if queued:
                        for q_msg in queued:
                            await send_json(q_msg)
                        logger.info(
                            "Delivered %d queued offline messages to %s",
                            len(queued), client_id,
                        )

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
                # Record heartbeat in sync service
                if client_id:
                    sync_service = get_sync_service()
                    await sync_service.record_heartbeat(client_id)
                await websocket.send_json({"type": "pong"})
                continue

            if msg.type == "hello":
                logger.info("Client hello received")
                continue

            # SYNC: Register session
            if msg.type == "sync.register":
                if user_id is None:
                    await send_json(
                        ChatErrorMessage(
                            type="chat.error",
                            message_id=None,
                            error="Not authenticated",
                        ).model_dump()
                    )
                    continue

                sync_service = get_sync_service()
                session_id = str(uuid.uuid4())
                raw_client_id = raw.get("client_id", f"ws_{user_id}_{session_id[:8]}")
                client_type = raw.get("client_type", "mobile")
                session_result = await sync_service.register_session(
                    session_id=session_id,
                    client_id=raw_client_id,
                    client_type=client_type,
                    user_id=user_id,
                )
                client_id = raw_client_id
                await send_json({
                    "type": "sync.registered",
                    "session_id": session_id,
                    "client_id": client_id,
                    "recovery_count": session_result.get("recovery_count", 0),
                    "requires_full_sync": session_result.get("requires_full_sync", False),
                    "queued_messages": session_result.get("queued_messages", []),
                })
                continue

            # SYNC: Heartbeat
            if msg.type == "sync.heartbeat":
                if client_id:
                    sync_service = get_sync_service()
                    await sync_service.record_heartbeat(client_id)
                await send_json({"type": "sync.heartbeat_ack"})
                continue

            # SYNC: Mark messages seen
            if msg.type == "sync.mark_seen":
                if client_id:
                    sync_service = get_sync_service()
                    message_ids = raw.get("message_ids", [])
                    await sync_service.mark_messages_seen_bulk(client_id, message_ids)
                continue

            # SYNC: Full sync request
            if msg.type == "sync.request":
                if user_id is None:
                    await send_json(
                        ChatErrorMessage(
                            type="chat.error",
                            message_id=None,
                            error="Not authenticated",
                        ).model_dump()
                    )
                    continue

                sync_service = get_sync_service()
                from dash_backend.sync.service import SyncRequest

                sync_request = SyncRequest(
                    client_id=raw.get("client_id", client_id or "unknown"),
                    client_type=raw.get("client_type", "mobile"),
                    last_sync_timestamp=raw.get("last_sync_timestamp"),
                    conversations_since=raw.get("conversations", []),
                    memories_since=raw.get("memories", []),
                    message_ids_seen=set(raw.get("message_ids_seen", [])),
                    vector_clock=raw.get("vector_clock", {}),
                )
                response = await sync_service.perform_full_sync(
                    user_id, sync_request.client_id, sync_request
                )
                await send_json({
                    "type": "sync.response",
                    "conversations": response.conversations,
                    "memories": response.memories,
                    "conflicts": response.conflicts,
                    "server_timestamp": response.server_timestamp,
                    "requires_full_sync": response.requires_full_sync,
                })
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

                from dash_backend.chat.service import (
                    add_message, create_conversation, get_conversation,
                    generate_conversation_title, get_user_conversations,
                    update_conversation
                )

                from dash_backend.db.session import AsyncSessionLocal
                from dash_backend.db.models.message import MessageRole

                async with AsyncSessionLocal() as session:
                    conversation = None
                    if chat_msg.conversation_id:
                        conversation = await get_conversation(
                            session, chat_msg.conversation_id
                        )

                    if conversation is None:
                        # Check if this is the user's first conversation
                        user_convs, _ = await get_user_conversations(session, user_id, limit=1)
                        is_first_conversation = len(user_convs) == 0
                        
                        conversation = await create_conversation(
                            session=session,
                            user_id=user_id,
                        )
                        
                        # Auto-title the first conversation based on the first message
                        if is_first_conversation:
                            title = await generate_conversation_title(
                                session, conversation.id, chat_msg.content
                            )
                            conversation = await update_conversation(
                                session, conversation.id, title=title
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
                        if hasattr(event, 'type') and event.type == 'chat.done':
                            event.conversation_id = str(conversation.id)
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
        # Unregister sync session
        if client_id:
            try:
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