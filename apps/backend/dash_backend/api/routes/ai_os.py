"""AI OS API routes.

Provides REST endpoints for:
  - Natural language command execution
  - Plan creation and management
  - Context/session management
  - Provider management
  - Permission management
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_os.executor import get_executor, AIExecutor
from dash_backend.services.ai_os.planner import get_planner
from dash_backend.services.ai_os.context_manager import get_context_manager
from dash_backend.services.command.models import CommandCategory, PermissionDecision
from dash_backend.services.command.service import get_command_service
from dash_backend.services.permissions import get_permission_service

logger = get_logger(__name__)

router = APIRouter(prefix="/ai-os", tags=["ai-os"])


# ── Request / Response Models ────────────────────────────────


class ExecuteRequest(BaseModel):
    text: str = Field(..., description="Natural language command")
    session_id: str = Field(default="", description="Session ID for context")
    user_id: str = Field(default="", description="User ID")
    auto_approve: bool = Field(default=False, description="Skip approval")


class ExecuteResponse(BaseModel):
    success: bool
    plan_id: str = ""
    command_id: str = ""
    steps_completed: int = 0
    steps_failed: int = 0
    summary: str = ""
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0


class PlanResponse(BaseModel):
    plan_id: str
    user_query: str
    steps: list[dict[str, Any]]
    status: str
    created_at: float


class SessionResponse(BaseModel):
    session_id: str
    current_project: str = ""
    current_application: str = ""
    last_command: str = ""
    recent_commands: list[dict[str, Any]] = Field(default_factory=list)
    recent_files: list[str] = Field(default_factory=list)
    user_id: str = ""


class ProviderRegisterResponse(BaseModel):
    status: str
    provider: str
    model: str = ""
    primary: bool = False


class ProviderListResponse(BaseModel):
    providers: list[dict[str, Any]]


class PermissionUpdateResponse(BaseModel):
    status: str
    category: str
    action: str


# ── Endpoints ────────────────────────────────────────────────


@router.post("/execute", response_model=ExecuteResponse)
async def execute_command(req: ExecuteRequest) -> dict[str, Any]:
    """Execute a natural language command through the AI OS pipeline."""
    executor = get_executor()
    result = await executor.execute(
        text=req.text,
        session_id=req.session_id,
        user_id=req.user_id,
        auto_approve=req.auto_approve,
    )
    return {
        "success": result.success,
        "plan_id": result.plan_id,
        "command_id": result.command_id,
        "steps_completed": result.steps_completed,
        "steps_failed": result.steps_failed,
        "summary": result.summary,
        "output": result.output,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans(limit: int = 10) -> list[dict[str, Any]]:
    """List recent execution plans."""
    planner = get_planner()
    plans = planner.list_plans(limit=limit)
    return [
        {
            "plan_id": p.plan_id,
            "user_query": p.user_query,
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "status": s.status,
                    "action": s.action,
                }
                for s in p.steps
            ],
            "status": p.status,
            "created_at": p.created_at,
        }
        for p in plans
    ]


@router.get("/plans/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str) -> dict[str, Any]:
    """Get a specific execution plan."""
    planner = get_planner()
    plan = planner.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return {
        "plan_id": plan.plan_id,
        "user_query": plan.user_query,
        "steps": [
            {
                "step_id": s.step_id,
                "description": s.description,
                "status": s.status,
                "action": s.action,
                "error": s.error,
            }
            for s in plan.steps
        ],
        "status": plan.status,
        "created_at": plan.created_at,
    }


@router.post("/plans/{plan_id}/cancel")
async def cancel_plan(plan_id: str) -> dict[str, Any]:
    """Cancel a running plan."""
    planner = get_planner()
    cancelled = planner.cancel_plan(plan_id)
    return {"cancelled": cancelled, "plan_id": plan_id}


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> dict[str, Any]:
    """Get session context."""
    ctx = get_context_manager()
    session = ctx.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    recent_commands = [
        {
            "command_id": c.command_id,
            "action": c.action,
            "category": c.category,
            "status": c.status,
        }
        for c in session.recent_commands[-10:]
    ]

    return {
        "session_id": session.session_id,
        "current_project": session.current_project,
        "current_application": session.current_application,
        "last_command": session.last_command,
        "recent_commands": recent_commands,
        "recent_files": session.recent_files[:10],
        "user_id": session.user_id,
    }


@router.post("/session/{session_id}/project")
async def set_current_project(session_id: str, project: str) -> dict[str, Any]:
    """Set the current project for a session."""
    ctx = get_context_manager()
    ctx.set_current_project(session_id, project)
    return {"status": "ok", "session_id": session_id, "project": project}


@router.post("/session/{session_id}/application")
async def set_current_application(session_id: str, application: str) -> dict[str, Any]:
    """Set the current application for a session."""
    ctx = get_context_manager()
    ctx.set_current_application(session_id, application)
    return {"status": "ok", "session_id": session_id, "application": application}


@router.get("/preferences/{user_id}")
async def get_preferences(user_id: str) -> dict[str, Any]:
    """Get all preferences for a user."""
    ctx = get_context_manager()
    return {"user_id": user_id, "preferences": ctx.get_all_preferences(user_id)}


@router.post("/preferences/{user_id}")
async def set_preference(user_id: str, key: str, value: Any) -> dict[str, Any]:
    """Set a user preference."""
    ctx = get_context_manager()
    ctx.set_preference(user_id, key, value)
    return {"status": "ok", "user_id": user_id, "key": key, "value": value}


@router.get("/providers", response_model=ProviderListResponse)
async def list_providers() -> dict[str, Any]:
    """List all registered AI providers with status."""
    from dash_backend.services.ai_providers.provider_manager import get_provider_manager

    pm = get_provider_manager()
    providers = pm.list_providers()
    return {"providers": providers}


@router.post("/providers/check-health")
async def check_providers_health() -> dict[str, Any]:
    """Check health of all AI providers."""
    from dash_backend.services.ai_providers.provider_manager import get_provider_manager

    pm = get_provider_manager()
    health = await pm.check_all_health()
    return {
        name: {
            "healthy": h.healthy,
            "latency_ms": h.latency_ms,
            "error": h.error,
            "model_loaded": h.model_loaded,
        }
        for name, h in health.items()
    }


@router.get("/permissions/{user_id}")
async def get_permissions(user_id: str) -> dict[str, Any]:
    """Get permission state for a user."""
    perm = get_permission_service()
    return {
        "user_id": user_id,
        "always_allowed": perm.get_allow_list(user_id),
        "always_denied": perm.get_deny_list(user_id),
    }


@router.post("/permissions/{user_id}/allow", response_model=PermissionUpdateResponse)
async def allow_command(user_id: str, category: str, action: str) -> dict[str, Any]:
    """Always allow a specific command for a user."""
    perm = get_permission_service()
    perm.add_always_allowed(user_id, category, action)
    return {"status": "ok", "category": category, "action": action}


@router.post("/permissions/{user_id}/deny", response_model=PermissionUpdateResponse)
async def deny_command(user_id: str, category: str, action: str) -> dict[str, Any]:
    """Forever deny a specific command for a user."""
    perm = get_permission_service()
    perm.add_denied_forever(user_id, category, action)
    return {"status": "ok", "category": category, "action": action}


@router.post("/approve/{command_id}")
async def approve_command(command_id: str, decision: str = "allow_once") -> dict[str, Any]:
    """Approve or reject a pending command.

    decision: allow_once, always_allow, deny, deny_forever
    """
    svc = get_command_service()
    decision_map = {
        "allow_once": PermissionDecision.ALLOW_ONCE,
        "always_allow": PermissionDecision.ALWAYS_ALLOW,
        "deny": PermissionDecision.DENY,
        "deny_forever": PermissionDecision.DENY_FOREVER,
    }
    d = decision_map.get(decision, PermissionDecision.ALLOW_ONCE)
    ok = await svc.approve(command_id, d)
    return {"approved": ok, "command_id": command_id, "decision": decision}
