"""Master Orchestrator REST API routes.

Exposes the Master Orchestrator over HTTP so complex, multi-step requests can be
decomposed into agent-assigned subtasks and executed in parallel.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.logging_config import get_logger
from dash_backend.orchestrator import get_master_orchestrator

logger = get_logger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ── Request / Response Models ────────────────────────────────


class OrchestrateRequest(BaseModel):
    request: str = Field(..., description="Natural language request or goal")
    conversation_id: str = Field(default="", description="Conversation ID")
    memory_context: str = Field(default="", description="Available memory context")
    max_tasks: int = Field(default=10, ge=1, le=20, description="Maximum subtasks")
    stream: bool = Field(default=False, description="Stream events to the client")


class OrchestrateResponse(BaseModel):
    request_id: str = ""
    goal: str = ""
    status: str = ""
    response: str = ""
    confidence: float = 0.0
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    agent_summary: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    duration_ms: int = 0
    reflection: Optional[Dict[str, Any]] = None


class OrchestratorStats(BaseModel):
    runs_started: int = 0
    runs_completed: int = 0
    runs_failed: int = 0
    tasks_executed: int = 0
    parallel_executions: int = 0


# ── Endpoints ────────────────────────────────────────────────


@router.post("/run", response_model=OrchestrateResponse)
async def orchestrate(
    req: OrchestrateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> Dict[str, Any]:
    """Run the Master Orchestrator on a request (non-streaming)."""
    orchestrator = get_master_orchestrator()
    user_id = str(current_user.id)

    final_result: Optional[OrchestrateResponse] = None
    async for event in orchestrator.run(
        request=req.request,
        user_id=user_id,
        conversation_id=req.conversation_id or None,
        memory_context=req.memory_context or None,
        max_tasks=req.max_tasks,
    ):
        if event.type == "orchestrator.completed":
            data = event.data
            final_result = OrchestrateResponse(**data)
        elif event.type == "orchestrator.failed":
            raise HTTPException(status_code=500, detail=event.data.get("error", "Orchestration failed"))

    if final_result is None:
        raise HTTPException(status_code=500, detail="Orchestration produced no result")

    return final_result.model_dump()


@router.post("/run/stream")
async def orchestrate_stream(
    req: OrchestrateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> StreamingResponse:
    """Run the Master Orchestrator and stream events (Server-Sent Events)."""
    orchestrator = get_master_orchestrator()
    user_id = str(current_user.id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in orchestrator.run(
            request=req.request,
            user_id=user_id,
            conversation_id=req.conversation_id or None,
            memory_context=req.memory_context or None,
            max_tasks=req.max_tasks,
        ):
            yield f"data: {event.to_json()}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stats", response_model=OrchestratorStats)
async def orchestrator_stats(
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> Dict[str, Any]:
    """Get Master Orchestrator statistics."""
    orchestrator = get_master_orchestrator()
    return orchestrator.get_stats()
