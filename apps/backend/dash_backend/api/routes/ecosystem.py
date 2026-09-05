"""Agent Ecosystem REST API routes.

Exposes read-only views of the DASH agent ecosystem and a dispatch endpoint so
the frontend (or external tools) can query the ecosystem status. This is
additive and does not replace the existing ``agents`` CRUD or the
``/orchestrator`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dash_backend.logging_config import get_logger
from dash_backend.agents.ecosystem.orchestrator_extension import get_ecosystem_state

logger = get_logger(__name__)

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])


# ── Request / Response Models ────────────────────────────────


class DispatchRequest(BaseModel):
    agent: str = Field(..., description="Ecosystem agent key (e.g. system_monitor)")
    action: str = Field(default="status", description="Agent action")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Agent payload")


# ── Endpoints ────────────────────────────────────────────────


@router.get("/agents")
async def list_ecosystem_agents(category: Optional[str] = None) -> Dict[str, Any]:
    """List all registered ecosystem agents (optionally by category)."""
    state = get_ecosystem_state()
    agents = state.list_ecosystem_agents(category)
    return {"agents": agents, "count": len(agents)}


@router.get("/agents/{agent_key}")
async def get_ecosystem_agent(agent_key: str) -> Dict[str, Any]:
    """Get a specific ecosystem agent spec + health/status."""
    state = get_ecosystem_state()
    spec = next((a for a in state.list_ecosystem_agents() if a["key"] == agent_key), None)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Ecosystem agent '{agent_key}' not found")

    # Provide runtime health/status where available.
    from dash_backend.agents.ecosystem.registry import get_agent_registry

    info: Dict[str, Any] = {"spec": spec}
    runtime = get_agent_registry().get_runtime(agent_key)
    if runtime is not None:
        info["health"] = await runtime.health()
        info["status"] = await runtime.status()
    return info


@router.post("/dispatch")
async def dispatch_agent(req: DispatchRequest) -> Dict[str, Any]:
    """Dispatch an action to an ecosystem agent."""
    state = get_ecosystem_state()
    payload = {**req.payload, "action": req.action}
    result = await state.dispatch_ecosystem_agent(req.agent, payload)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Ecosystem agent '{req.agent}' not found")
    return result


@router.get("/task-memory")
async def list_task_memory(limit: int = 50) -> Dict[str, Any]:
    """List recently recorded task memory records."""
    state = get_ecosystem_state()
    records = state.task_memory.list(limit=limit)
    return {"records": records, "count": len(records)}


@router.get("/improvement")
async def list_improvement() -> Dict[str, Any]:
    """List learned strategies (self-improvement store)."""
    state = get_ecosystem_state()
    strategies = state.improvement.list()
    return {"strategies": strategies, "count": len(strategies)}
