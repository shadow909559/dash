"""WebSocket endpoints for real-time communication with sync support."""

import asyncio
import json
import os
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.api.websocket.handlers import (
    handle_agent_run,
    handle_chat_send,
    handle_desktop_keyboard_hotkey,
    handle_desktop_keyboard_press,
    handle_desktop_keyboard_type,
    handle_desktop_mouse_click,
    handle_desktop_mouse_move,
    handle_desktop_mouse_scroll,
    handle_desktop_power_lock,
    handle_desktop_power_restart,
    handle_desktop_power_shutdown,
    handle_desktop_power_sleep,
    handle_phone_apps_get,
    handle_phone_apps_open,
    handle_phone_clipboard_get,
    handle_phone_clipboard_set,
    handle_phone_flashlight_toggle,
    handle_phone_media_next,
    handle_phone_media_pause,
    handle_phone_media_play,
    handle_phone_media_previous,
    handle_phone_notifications_clear,
    handle_phone_notifications_get,
    handle_phone_state,
    handle_phone_volume_get,
    handle_phone_volume_mute,
    handle_phone_volume_set,
    handle_voice_stt,
    handle_voice_tts,
)
from dash_backend.api.websocket.protocol import (
    ChatSendMessage,
    VoiceSTTMessage,
    VoiceTTSMessage,
    parse_client_message,
)
from dash_backend.db.session import AsyncSessionLocal
from dash_backend.logging_config import get_logger
from dash_backend.security.local_identity import verify_device_token, extract_ws_token

router = APIRouter()
logger = get_logger(__name__)

WS_UNAUTHORIZED_CODE = 4401


async def _resolve_owner_user_id() -> str:
    """Return the single owner user id (server-side data anchor)."""
    from dash_backend.auth.dependencies import resolve_owner_user

    async with AsyncSessionLocal() as session:
        user = await resolve_owner_user(session)
        return str(user.id)


async def _stream_logs(websocket: WebSocket, component: str, disconnected_flag) -> None:
    """Stream log file tail to the WebSocket client."""
    import os
    from dash_backend.logging_config import LOG_DIR, COMPONENT_LOGS

    log_file = COMPONENT_LOGS.get(component, "backend.log")
    log_path = os.path.join(LOG_DIR, log_file)

    if not os.path.exists(log_path):
        try:
            await websocket.send_json({"type": "logs.error", "error": f"Log file not found: {log_file}"})
        except Exception:
            pass
        return

    lines_sent = 0
    try:
        # Send last 30 lines
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            recent = all_lines[-30:] if len(all_lines) > 30 else all_lines
            for line in recent:
                if disconnected_flag:
                    return
                await websocket.send_json({"type": "logs.line", "line": line.rstrip(), "component": component})
                lines_sent += 1

        await websocket.send_json({"type": "logs.ready", "component": component})

        # Tail new lines every 3 seconds
        while not disconnected_flag:
            await asyncio.sleep(3)
            try:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    new_lines = f.readlines()
                    if len(new_lines) > lines_sent:
                        for line in new_lines[lines_sent:]:
                            if disconnected_flag:
                                return
                            await websocket.send_json({"type": "logs.line", "line": line.rstrip(), "component": component})
                        lines_sent = len(new_lines)
            except Exception:
                pass
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time DASH websocket with keepalive, chat, voice, and agent support.

    Authentication is mandatory: the handshake must carry the local device
    token (query `token` or header `x-dash-token`). Unauthenticated sockets
    are rejected before being accepted. There is no guest fallback.
    """
    if not verify_device_token(extract_ws_token(websocket)):
        client_host = websocket.client.host if websocket.client else "unknown"
        logger.warning("Rejected WebSocket connection from %s: missing/invalid device token", client_host)
        await websocket.close(code=WS_UNAUTHORIZED_CODE)
        return

    await websocket.accept()
    logger.info("WebSocket connected (device authenticated)")

    user_id = await _resolve_owner_user_id()
    # Greet immediately: desktop clients treat session.info as proof of
    # authentication and will not send anything until they receive it.
    client_id: str | None = str(uuid.uuid4())
    disconnected = False

    async def send_json(data: object) -> None:
        if disconnected:
            return
        try:
            await websocket.send_json(data)
        except (WebSocketDisconnect, Exception):
            pass

    try:
        from dash_backend.api.routes.notifications import register_websocket

        register_websocket(user_id, websocket)
    except Exception:
        logger.exception("Failed to register WebSocket for notifications")

    # ── Start notification listener — push system notifications to this client ──
    async def _push_notification(notification: dict) -> None:
        await send_json({
            "type": "notification.push",
            "notification": notification,
        })

    try:
        from dash_backend.services.notification_listener import get_notification_listener
        listener = get_notification_listener()
        listener.on_notification(_push_notification)
        if not listener._running:
            listener.start()
    except Exception:
        logger.exception("Failed to start notification listener")

    await send_json({"type": "session.info", "session_id": client_id, "client_id": client_id})

    # ── Push system metrics every 3 seconds ──
    async def _system_metrics_loop() -> None:
        try:
            from dash_backend.services.system.system_info import get_system_info
            from dash_backend.services.system.hardware import get_cpu_info, get_ram_info
            from dash_backend.services.system.gpu import get_gpu_info
            while True:
                try:
                    info = await asyncio.to_thread(get_system_info)
                    # Add real hardware metrics so mobile displays them
                    try:
                        cpu = await asyncio.to_thread(get_cpu_info)
                        info["cpu_percent"] = cpu.get("percent") or 0
                    except Exception:
                        info["cpu_percent"] = 0
                    try:
                        ram = await asyncio.to_thread(get_ram_info)
                        info["memory_percent"] = ram.get("percent") or 0
                        info["memory_total_gb"] = ram.get("total_gb", 0)
                        info["memory_used_gb"] = ram.get("used_gb", 0)
                    except Exception:
                        info["memory_percent"] = 0
                    try:
                        gpu_raw = await asyncio.to_thread(get_gpu_info)
                        gpu = gpu_raw[0] if isinstance(gpu_raw, list) and gpu_raw else (gpu_raw if isinstance(gpu_raw, dict) else {})
                        info["gpu_usage"] = gpu.get("usage_percent") or 0
                        info["gpu_name"] = gpu.get("name", "")
                        info["gpu_memory_used_mb"] = gpu.get("memory_used_mb") or 0
                        info["gpu_memory_total_mb"] = gpu.get("memory_total_mb") or 0
                    except Exception:
                        info["gpu_usage"] = 0
                    # Disk info
                    try:
                        import psutil
                        disk = psutil.disk_usage('\\')
                        info["disk_percent"] = disk.percent
                        info["disk_total_gb"] = round(disk.total / (1024**3), 1)
                        info["disk_used_gb"] = round(disk.used / (1024**3), 1)
                    except Exception:
                        info["disk_percent"] = 0
                    await send_json({
                        "type": "system",
                        "data": info,
                    })
                except Exception:
                    pass
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    system_task = asyncio.create_task(_system_metrics_loop())

    async def keepalive_loop() -> None:
        nonlocal disconnected
        while not disconnected:
            await asyncio.sleep(30)
            if disconnected:
                break
            try:
                # Send passive pong to keep connection alive
                await websocket.send_json({"type": "pong"})
            except (WebSocketDisconnect, Exception):
                break

    keepalive_task = asyncio.create_task(keepalive_loop())
    chat_tasks: set[asyncio.Task[None]] = set()

    async def process_chat(chat_msg: ChatSendMessage) -> None:
        assistant_content = ""
        request_id = chat_msg.message_id or str(uuid.uuid4())
        chat_msg.message_id = request_id

        from dash_backend.chat.service import add_message, create_conversation
        from dash_backend.db.models.message import MessageRole

        logger.info(
            "Chat request: user=%s message_id=%s conversation_id=%s",
            user_id,
            request_id,
            chat_msg.conversation_id,
        )

        try:
            # Get the actual model being used from provider manager
            from dash_backend.llm.provider_manager import get_ollama_manager
            ollama_manager = get_ollama_manager()
            model_name = ollama_manager.get_configured_model() or "AI"
            
            await send_json({
                "type": "chat.status",
                "message_id": request_id,
                "status": "thinking",
                "detail": f"{model_name.upper()} PROCESSING...",
            })
        except Exception as exc:
            logger.exception("Failed to send thinking status for message_id=%s: %s", request_id, exc)

        try:
            async with AsyncSessionLocal() as session:
                if not chat_msg.conversation_id:
                    conv = await create_conversation(session, user_id)
                    chat_msg.conversation_id = str(conv.id)
                await add_message(session, chat_msg.conversation_id, MessageRole.USER, chat_msg.content)
        except Exception as exc:
            logger.exception("Failed to persist user message message_id=%s: %s", request_id, exc)
            try:
                await send_json({
                    "type": "chat.error",
                    "message_id": request_id,
                    "error": "Failed to save your message.",
                })
            except Exception:
                pass
            return

        # ── Autonomous brain: route through the JARVIS orchestrator ──
        agent_prefixes = ("agent:", "autonomous:", "do:", "go:", "execute:")
        is_agent_msg = chat_msg.content.lower().strip().startswith(agent_prefixes)
        is_complex = not is_agent_msg  # let the brain decide for non-prefixed messages

        if is_agent_msg:
            # Strip prefix
            goal_desc = chat_msg.content
            for prefix in agent_prefixes:
                if chat_msg.content.lower().strip().startswith(prefix):
                    goal_desc = chat_msg.content[len(prefix):].strip()
                    break
            chat_msg.content = goal_desc

        try:
            from dash_backend.autonomous.brain import get_brain
            brain = get_brain()
            response = await brain.handle_chat(chat_msg.content, user_id)
            assistant_content = response
            await send_json({"type": "chat.token", "message_id": request_id, "content": response})
            await send_json({"type": "chat.done", "message_id": request_id, "conversation_id": chat_msg.conversation_id})
            try:
                async with AsyncSessionLocal() as save_session:
                    await add_message(save_session, chat_msg.conversation_id, MessageRole.ASSISTANT, assistant_content)
            except Exception:
                pass
            # Auto-TTS: speak the response so DASH talks like JARVIS
            try:
                from dash_backend.voice import synthesize_text
                tts_text = response[:500]  # cap for TTS to avoid long syntheses
                audio_b64 = await synthesize_text(tts_text, provider_name="piper", user_id=user_id)
                if audio_b64:
                    await send_json({
                        "type": "voice.tts_ready",
                        "message_id": request_id,
                        "audio_base64": audio_b64,
                    })
            except Exception as exc:
                logger.debug("Auto-TTS failed for brain response: %s", exc)
        except Exception as exc:
            logger.exception("Brain chat failed: %s", exc)
            await send_json({"type": "chat.token", "message_id": request_id, "content": f"I encountered an issue: {exc}"})
            await send_json({"type": "chat.done", "message_id": request_id, "conversation_id": chat_msg.conversation_id})
        return

        # ── Command interception: detect desktop-control commands ──
        try:
            from dash_backend.services.command_interceptor import try_intercept
            cmd_result = await try_intercept(chat_msg.content)
            if cmd_result is not None:
                # Command was executed — send result directly, skip LLM
                summary = cmd_result.get("summary", "Command executed")
                assistant_content = summary
                await send_json({
                    "type": "chat.status",
                    "message_id": request_id,
                    "status": "executing",
                    "detail": summary,
                })
                await send_json({
                    "type": "chat.token",
                    "message_id": request_id,
                    "content": summary,
                })
                await send_json({
                    "type": "chat.done",
                    "message_id": request_id,
                    "conversation_id": chat_msg.conversation_id,
                })
                # Persist assistant response
                try:
                    async with AsyncSessionLocal() as save_session:
                        await add_message(
                            save_session,
                            chat_msg.conversation_id,
                            MessageRole.ASSISTANT,
                            assistant_content,
                        )
                except Exception as exc:
                    logger.exception("Failed to save command response: %s", exc)
                # Auto-TTS for voice feedback
                try:
                    from dash_backend.voice import synthesize_text
                    audio_b64 = await synthesize_text(summary, provider_name="piper", user_id=user_id)
                    if audio_b64:
                        await send_json({
                            "type": "voice.tts_ready",
                            "message_id": request_id,
                            "audio_base64": audio_b64,
                        })
                except Exception as exc:
                    logger.exception("Auto-TTS failed for command: %s", exc)
                logger.info("Command intercepted and executed: %s -> %s", chat_msg.content, summary)
                return  # Skip normal LLM flow
        except Exception as exc:
            logger.exception("Command interceptor failed: %s — falling through to LLM", exc)

        try:
            try:
                await send_json({
                    "type": "chat.status",
                    "message_id": request_id,
                    "status": "responding",
                })
            except Exception as exc:
                logger.exception("Failed to send responding status for message_id=%s: %s", request_id, exc)

            async with AsyncSessionLocal() as session:
                async for event in handle_chat_send(chat_msg, session=session, user_id=user_id):
                    if event.type == "chat.token":
                        assistant_content += event.content
                    if event.type == "chat.done":
                        event.conversation_id = chat_msg.conversation_id
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
                    try:
                        await send_json(event.model_dump())
                    except Exception as exc:
                        logger.exception("Failed to send event for message_id=%s: %s", request_id, exc)

            logger.info("Completed chat response for user=%s message_id=%s", user_id, request_id)

            if assistant_content and assistant_content.strip():
                try:
                    from dash_backend.voice import synthesize_text
                    audio_b64 = await synthesize_text(assistant_content, provider_name="piper", user_id=user_id)
                    if audio_b64:
                        try:
                            await send_json({
                                "type": "voice.tts_ready",
                                "message_id": chat_msg.message_id,
                                "audio_base64": audio_b64,
                            })
                            logger.info("Auto-TTS completed for response message_id=%s", request_id)
                        except Exception as exc:
                            logger.exception("Failed to send TTS audio for message_id=%s: %s", request_id, exc)
                except Exception as exc:
                    logger.exception("Auto-TTS failed for assistant response message_id=%s: %s", request_id, exc)

        except Exception as exc:
            logger.exception("Chat handler failed for message_id=%s: %s", request_id, exc)
            try:
                await send_json({
                    "type": "chat.error",
                    "message_id": request_id,
                    "error": "An internal error occurred while processing your request.",
                })
            except Exception:
                pass

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

            # Heartbeat — respond to client ping/pong keepalive FIRST so this
            # stays an internal protocol exchange and never reaches the normal
            # command/agent error handling branch (no "Unsupported: ping").
            if msg_type in ("ping", "heartbeat"):
                # Respond immediately to client ping
                await send_json({"type": "pong"})
                continue

            # Parse typed message
            try:
                msg = parse_client_message(raw)
            except ValueError as exc:
                await send_json({"type": "chat.error", "message_id": None, "error": str(exc)})
                continue

            # Chat send — run in a background task so ping/pong still works
            # while the LLM is generating (otherwise the receive loop is blocked
            # and the client treats the socket as stale).
            if msg_type == "chat.send":
                chat_msg = msg if isinstance(msg, ChatSendMessage) else ChatSendMessage.model_validate(raw)
                task = asyncio.create_task(process_chat(chat_msg))
                chat_tasks.add(task)
                task.add_done_callback(chat_tasks.discard)
                continue

            # Voice STT → brain → TTS (full JARVIS cycle)
            elif msg_type == "voice.interact":
                audio_b64 = msg.get("audio_base64", "")
                if audio_b64:
                    try:
                        import base64
                        from dash_backend.voice import transcribe_audio, synthesize_text
                        from dash_backend.autonomous.brain import get_brain
                        # Transcribe
                        audio_bytes = base64.b64decode(audio_b64)
                        transcript = await transcribe_audio(audio_bytes)
                        if transcript and len(transcript.strip()) > 1:
                            await send_json({"type": "voice.transcript", "text": transcript})
                            # Brain processes it
                            brain = get_brain()
                            response = await brain.handle_chat(transcript, user_id, voice_mode=True)
                            await send_json({"type": "chat.token", "message_id": str(uuid.uuid4()), "content": response})
                            # Synthesize response
                            tts_audio = await synthesize_text(response[:500], provider_name="piper")
                            if tts_audio:
                                await send_json({"type": "voice.tts_ready", "audio_base64": tts_audio})
                    except Exception as exc:
                        logger.debug("Voice interact failed: %s", exc)
                        await send_json({"type": "voice.error", "error": str(exc)})

            # Voice STT (standalone)
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

            # Log streaming
            elif msg_type == "logs.subscribe":
                component = raw.get("component", "backend")
                await send_json({"type": "logs.subscribed", "component": component})
                # Start streaming logs in background
                log_task = asyncio.create_task(_stream_logs(websocket, component, disconnected))
                chat_tasks.add(log_task)
                log_task.add_done_callback(chat_tasks.discard)

            # Hello — client introduction; session info already sent above.
            elif msg_type == "hello":
                logger.info("Client hello: %s", getattr(msg, "client", "unknown"))

            # Tool confirmation flow (pending confirmations live in the
            # global ToolManager singleton used by the chat pipeline).
            elif msg_type == "tool.confirmed":
                from dash_backend.tools.tool_manager import get_tool_manager

                token = getattr(msg, "confirmation_token", None)
                if not token:
                    await send_json({
                        "type": "chat.error",
                        "message_id": None,
                        "error": "Missing confirmation_token",
                    })
                else:
                    async for event_type, data in get_tool_manager().confirm_execution(token):
                        payload = {"type": event_type}
                        payload.update(data)
                        await send_json(payload)

            elif msg_type == "tool.rejected":
                from dash_backend.tools.tool_manager import get_tool_manager

                token = getattr(msg, "confirmation_token", None)
                if not token:
                    await send_json({
                        "type": "chat.error",
                        "message_id": None,
                        "error": "Missing confirmation_token",
                    })
                else:
                    data = await get_tool_manager().reject_execution(token)
                    payload = {"type": "tool.rejected"}
                    payload.update(data)
                    await send_json(payload)

            # Phone integration (from the mobile companion app)
            elif msg_type == "phone.state":
                async for event in handle_phone_state(msg):
                    await send_json(event)
            elif msg_type == "phone.clipboard.get":
                async for event in handle_phone_clipboard_get(msg):
                    await send_json(event)
            elif msg_type == "phone.clipboard.set":
                async for event in handle_phone_clipboard_set(msg):
                    await send_json(event)
            elif msg_type == "phone.volume.get":
                async for event in handle_phone_volume_get(msg):
                    await send_json(event)
            elif msg_type == "phone.volume.set":
                async for event in handle_phone_volume_set(msg):
                    await send_json(event)
            elif msg_type == "phone.volume.mute":
                async for event in handle_phone_volume_mute(msg):
                    await send_json(event)
            elif msg_type == "phone.flashlight.toggle":
                async for event in handle_phone_flashlight_toggle(msg):
                    await send_json(event)
            elif msg_type == "phone.notifications.get":
                async for event in handle_phone_notifications_get(msg):
                    await send_json(event)
            elif msg_type == "phone.notifications.clear":
                async for event in handle_phone_notifications_clear(msg):
                    await send_json(event)
            elif msg_type == "phone.apps.get":
                async for event in handle_phone_apps_get(msg):
                    await send_json(event)
            elif msg_type == "phone.apps.open":
                async for event in handle_phone_apps_open(msg):
                    await send_json(event)
            elif msg_type == "phone.media.play":
                async for event in handle_phone_media_play(msg):
                    await send_json(event)
            elif msg_type == "phone.media.pause":
                async for event in handle_phone_media_pause(msg):
                    await send_json(event)
            elif msg_type == "phone.media.next":
                async for event in handle_phone_media_next(msg):
                    await send_json(event)
            elif msg_type == "phone.media.previous":
                async for event in handle_phone_media_previous(msg):
                    await send_json(event)

            # Desktop control from phone
            elif msg_type == "desktop.mouse.move":
                async for event in handle_desktop_mouse_move(msg):
                    await send_json(event)
            elif msg_type == "desktop.mouse.click":
                async for event in handle_desktop_mouse_click(msg):
                    await send_json(event)
            elif msg_type == "desktop.mouse.scroll":
                async for event in handle_desktop_mouse_scroll(msg):
                    await send_json(event)
            elif msg_type == "desktop.keyboard.type":
                async for event in handle_desktop_keyboard_type(msg):
                    await send_json(event)
            elif msg_type == "desktop.keyboard.press":
                async for event in handle_desktop_keyboard_press(msg):
                    await send_json(event)
            elif msg_type == "desktop.keyboard.hotkey":
                async for event in handle_desktop_keyboard_hotkey(msg):
                    await send_json(event)
            elif msg_type == "desktop.power.shutdown":
                async for event in handle_desktop_power_shutdown(msg):
                    await send_json(event)
            elif msg_type == "desktop.power.restart":
                async for event in handle_desktop_power_restart(msg):
                    await send_json(event)
            elif msg_type == "desktop.power.lock":
                async for event in handle_desktop_power_lock(msg):
                    await send_json(event)
            elif msg_type == "desktop.power.sleep":
                async for event in handle_desktop_power_sleep(msg):
                    await send_json(event)

            # Server->client-only statuses; nothing to do.
            elif msg_type in ("ai.provider.status", "pong"):
                pass

            # Android command messages
            elif msg_type == "command":
                from dash_backend.api.routes.commands import execute_command
                command = raw.get("command")
                command_id = raw.get("command_id")
                payload = raw.get("payload", {})
                try:
                    result = await execute_command(command, payload)
                    await send_json({
                        "type": "command_result",
                        "command_id": command_id,
                        "success": True,
                        "result": json.dumps(result),
                    })
                except ValueError as e:
                    logger.warning("Unknown command: %s", command)
                    await send_json({"type": "command_result", "command_id": command_id, "success": False, "error": str(e)})
                    continue
                except Exception as e:
                    logger.exception("Command %s failed: %s", command, e)
                    await send_json({"type": "command_result", "command_id": command_id, "success": False, "error": str(e)})

            # ── Bidirectional notification: mobile → desktop & other clients ──
            elif msg_type == "notification.send":
                title = raw.get("title", "DASH")
                message = raw.get("message", "")
                notif_type = raw.get("notif_type", "info")
                try:
                    from dash_backend.api.routes.notifications import broadcast_notification, send_notification
                    notif = await send_notification(user_id, title, message, notif_type)
                    await send_json({
                        "type": "notification.ack",
                        "notification_id": notif["id"],
                        "status": "forwarded",
                    })
                    logger.info("Notification forwarded from mobile: %s - %s", title, message)
                except Exception as exc:
                    logger.exception("Failed to forward notification: %s", exc)
                    await send_json({"type": "chat.error", "message_id": None, "error": f"Notification failed: {exc}"})

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
        system_task.cancel()
        keepalive_task.cancel()
        for task in list(chat_tasks):
            task.cancel()
        try:
            await system_task
        except asyncio.CancelledError:
            pass
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass