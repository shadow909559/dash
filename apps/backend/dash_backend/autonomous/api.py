"""Autonomous Agent API — REST + WebSocket endpoints for controlling DASH's agent.

Endpoints:
    POST /api/v1/agent/goal       — Start a new autonomous goal
    GET  /api/v1/agent/goals      — List all goals
    GET  /api/v1/agent/goal/{id}  — Get goal status
    POST /api/v1/agent/goal/{id}/pause   — Pause a goal
    POST /api/v1/agent/goal/{id}/cancel  — Cancel a goal
    WS   /ws/agent                — Real-time goal streaming
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.logging_config import get_logger
from dash_backend.security.local_identity import verify_device_token, extract_ws_token
from fastapi import HTTPException

logger = get_logger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])
WS_UNAUTHORIZED_CODE = 4401

# Active WebSocket subscribers for agent events
_agent_subscribers: dict[str, WebSocket] = {}


# ── Request Models ────────────────────────────────────────────────────────

class GoalRequest(BaseModel):
    description: str
    context: dict[str, Any] = {}
    max_iterations: int = 30
    timeout: float = 300.0


# ── REST Endpoints ────────────────────────────────────────────────────────

@router.post("/goal")
async def start_goal(req: GoalRequest, user_id: str = __import__("fastapi").Depends(get_current_user_id)):
    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()

    goal = await core.run_goal(
        description=req.description,
        context={**req.context, "user_id": user_id},
        max_iterations=req.max_iterations,
        timeout=req.timeout,
    )
    return {"goal_id": goal.id, "status": goal.state.value}


@router.get("/goals")
async def list_goals(user_id: str = __import__("fastapi").Depends(get_current_user_id)):
    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()
    return {"goals": core.list_goals()}


@router.get("/goal/{goal_id}")
async def get_goal(goal_id: str, user_id: str = __import__("fastapi").Depends(get_current_user_id)):
    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()
    goal = core.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal.to_dict()


@router.post("/goal/{goal_id}/pause")
async def pause_goal(goal_id: str, user_id: str = __import__("fastapi").Depends(get_current_user_id)):
    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()
    ok = await core.pause_goal(goal_id)
    return {"success": ok}


@router.post("/goal/{goal_id}/cancel")
async def cancel_goal(goal_id: str, user_id: str = __import__("fastapi").Depends(get_current_user_id)):
    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()
    ok = await core.cancel_goal(goal_id)
    return {"success": ok}


@router.get("/memory")
async def get_memory(user_id: str = __import__("fastapi").Depends(get_current_user_id)):
    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()
    return {"memory": core.get_working_memory()}


# ── WebSocket for real-time agent events ──────────────────────────────────

@router.websocket("/ws")
async def agent_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time autonomous agent streaming.

    Client sends:
        { "type": "agent.start", "description": "...", "context": {...} }
        { "type": "agent.pause", "goal_id": "..." }
        { "type": "agent.cancel", "goal_id": "..." }
        { "type": "agent.goals" }
        { "type": "ping" }

    Server sends:
        { "type": "agent.goal.started", "goal": {...} }
        { "type": "agent.goal.step", "goal_id": "...", "step": N, ... }
        { "type": "agent.goal.completed", "goal": {...} }
        { "type": "agent.goal.failed", "goal": {...} }
        { "type": "agent.goals", "goals": [...] }
        { "type": "pong" }
    """
    if not verify_device_token(extract_ws_token(websocket)):
        await websocket.close(code=WS_UNAUTHORIZED_CODE)
        return

    await websocket.accept()
    subscriber_id = str(uuid.uuid4())
    _agent_subscribers[subscriber_id] = websocket
    logger.info("Agent WS connected: %s", subscriber_id)

    from dash_backend.autonomous.agent_core import get_agent_core
    core = get_agent_core()

    # Register callback to stream events to this WebSocket
    async def stream_event(event: str, data: dict):
        ws = _agent_subscribers.get(subscriber_id)
        if ws:
            try:
                await ws.send_json({"type": f"agent.{event}", **data})
            except Exception:
                _agent_subscribers.pop(subscriber_id, None)

    unsubscribe = core.on_step(stream_event)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "Invalid JSON"})
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "agent.start":
                desc = msg.get("description", "")
                ctx = msg.get("context", {})
                max_iter = msg.get("max_iterations", 30)
                timeout_s = msg.get("timeout", 300.0)
                goal = await core.run_goal(desc, ctx, max_iter, timeout_s)
                # Ack only — the core's _notify callback broadcasts the event

            elif msg_type == "agent.pause":
                goal_id = msg.get("goal_id", "")
                ok = await core.pause_goal(goal_id)
                await websocket.send_json({"type": "agent.paused", "success": ok})

            elif msg_type == "agent.cancel":
                goal_id = msg.get("goal_id", "")
                ok = await core.cancel_goal(goal_id)
                await websocket.send_json({"type": "agent.cancelled", "success": ok})

            elif msg_type == "agent.goals":
                goals = core.list_goals()
                await websocket.send_json({"type": "agent.goals", "goals": goals})

            elif msg_type == "agent.memory":
                mem = core.get_working_memory()
                await websocket.send_json({"type": "agent.memory", "memory": mem})

            else:
                await websocket.send_json({"type": "error", "error": f"Unknown: {msg_type}"})

    except WebSocketDisconnect:
        logger.info("Agent WS disconnected: %s", subscriber_id)
    except Exception as exc:
        logger.debug("Agent WS error: %s", exc)
    finally:
        unsubscribe()
        _agent_subscribers.pop(subscriber_id, None)
