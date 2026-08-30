"""Neural Core REST API — exposes the AI Brain to clients.

Endpoints under ``/brain``:
- POST /brain/process        — run the full neural pipeline on a request
- GET  /brain/habits         — user-model habit profile
- POST /brain/observe        — record a user observation
- GET  /brain/predictions    — predicted next actions
- GET  /brain/proactive      — proactive suggestions
- POST /brain/proactive/dismiss
- GET  /brain/goals          — tracked long-term goals
- POST /brain/goals          — add a long-term goal
- PATCH /brain/goals/{name}  — update goal status
- POST /brain/goals/{name}/milestones — complete a milestone
- POST /brain/prioritize     — classify tasks by urgency/importance
- GET  /brain/self-improvement — workflow analysis
- POST /brain/self-improvement/record — record an execution outcome

All endpoints are additive and use the existing ``memories`` table for
persistence (no new tables).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger
from dash_backend.neural.core import get_neural_core
from dash_backend.neural.user_model import get_user_model_engine
from dash_backend.neural.predictive import get_predictive_engine
from dash_backend.neural.proactive import get_proactive_engine
from dash_backend.neural.long_term_goals import get_long_term_goals_engine
from dash_backend.neural.prioritization import get_prioritization_engine
from dash_backend.neural.self_improvement import get_self_improvement_engine
from dash_backend.neural.personality import PersonalityEngine
from dash_backend.neural.context_engine import get_context_engine
from dash_backend.neural.continuity import get_continuity_engine
from dash_backend.neural.self_monitoring import get_self_monitoring_engine
from dash_backend.neural.error_handling import get_error_handling_engine
from dash_backend.neural.project_awareness import get_project_awareness_engine
from dash_backend.neural.multitasking import get_multitasking_engine
from dash_backend.neural.productivity import get_productivity_engine
from dash_backend.neural.autonomous_improvement import get_autonomous_improvement_engine

logger = get_logger(__name__)

router = APIRouter(prefix="/brain", tags=["brain"])


# ── Request / Response Models ────────────────────────────────────────


class ProcessRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    response: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    execution_success: Optional[bool] = None
    execution_error: str = ""
    execution_duration_s: float = 0.0


class ObserveRequest(BaseModel):
    event_type: str = Field(..., description="command | activity | folder | contact | coding | tool")
    payload: Dict[str, Any] = Field(default_factory=dict)


class GoalCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    milestones: List[str] = Field(default_factory=list)
    priority: str = "important"
    domains: List[str] = Field(default_factory=list)


class GoalStatusRequest(BaseModel):
    status: str = Field(..., description="active | paused | completed | abandoned")


class MilestoneRequest(BaseModel):
    milestone: str = Field(..., min_length=1)


class PrioritizeRequest(BaseModel):
    tasks: List[str] = Field(..., min_length=1)
    deadlines: Optional[Dict[str, float]] = None


class RecordExecutionRequest(BaseModel):
    task: str = Field(..., min_length=1)
    success: bool
    duration_s: float = 0.0
    error: str = ""
    strategy: str = ""
    domain: str = "general"


class ContextUpdateRequest(BaseModel):
    project: Optional[str] = None
    repository: Optional[str] = None
    language: Optional[str] = None
    folder: Optional[str] = None
    file: Optional[str] = None
    search: Optional[str] = None
    browser_tabs: Optional[List[str]] = None
    running_services: Optional[List[str]] = None
    task: Optional[str] = None


class ContinuitySnapshotRequest(BaseModel):
    conversation_topic: Optional[str] = None
    open_tasks: Optional[List[Dict[str, Any]]] = None
    running_workflows: Optional[List[Dict[str, Any]]] = None
    agent_state: Optional[Dict[str, Any]] = None
    desktop_state: Optional[Dict[str, Any]] = None
    orb_state: Optional[Dict[str, Any]] = None
    voice_state: Optional[Dict[str, Any]] = None


class HealthCheckRequest(BaseModel):
    readings: Optional[Dict[str, Any]] = None


class ErrorExplainRequest(BaseModel):
    error: str = Field(..., min_length=1)
    context: str = ""


class ProjectScanRequest(BaseModel):
    root: str = Field(..., min_length=1)


class MultitaskRequest(BaseModel):
    request: str = Field(..., min_length=1)
    max_concurrency: int = 4


class SessionRequest(BaseModel):
    task: str = ""
    category: str = "general"


class ImprovementDetectRequest(BaseModel):
    observations: Dict[str, Any] = Field(default_factory=dict)


class ImprovementApplyRequest(BaseModel):
    description: str = Field(..., min_length=1)


# ── Endpoints ────────────────────────────────────────────────────────


@router.post("/process")
async def brain_process(
    req: ProcessRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Run the full neural pipeline on a request."""
    core = get_neural_core()
    result = core.process(
        req.query,
        str(user.id),
        response=req.response,
        context=req.context,
        execution_success=req.execution_success,
        execution_error=req.execution_error,
        execution_duration_s=req.execution_duration_s,
    )
    return result.to_dict()


@router.get("/habits")
async def brain_habits(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the user-model habit profile."""
    engine = get_user_model_engine()
    return engine.get_habits(str(user.id)).to_dict()


@router.post("/observe")
async def brain_observe(
    req: ObserveRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Record a user observation for habit learning."""
    engine = get_user_model_engine()
    engine.observe(str(user.id), req.event_type, req.payload)
    return {"status": "ok", "event_type": req.event_type}


@router.get("/predictions")
async def brain_predictions(
    user: User = Depends(get_current_user),
    limit: int = 5,
) -> Dict[str, Any]:
    """Return predicted next actions for the user."""
    engine = get_predictive_engine()
    predictions = engine.predict_sequence(str(user.id), limit=limit)
    return {
        "predictions": [p.to_dict() for p in predictions],
        "sequences": engine.sequences(str(user.id), limit=10),
    }


@router.get("/proactive")
async def brain_proactive(
    user: User = Depends(get_current_user),
    limit: int = 10,
) -> Dict[str, Any]:
    """Return proactive suggestions for the user."""
    engine = get_proactive_engine()
    suggestions = engine.get(limit=limit)
    return {"suggestions": [s.to_dict() for s in suggestions]}


@router.post("/proactive/dismiss")
async def brain_proactive_dismiss(
    title: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Dismiss a proactive suggestion by title."""
    engine = get_proactive_engine()
    dismissed = engine.dismiss(title)
    return {"dismissed": dismissed, "title": title}


@router.get("/goals")
async def brain_goals(
    user: User = Depends(get_current_user),
    include_completed: bool = False,
) -> Dict[str, Any]:
    """Return tracked long-term goals."""
    engine = get_long_term_goals_engine()
    goals = engine.get_goals(str(user.id), include_completed=include_completed)
    return {"goals": [g.to_dict() for g in goals]}


@router.post("/goals")
async def brain_goals_create(
    req: GoalCreateRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Add a new long-term goal."""
    engine = get_long_term_goals_engine()
    goal = engine.add_goal(
        str(user.id),
        req.name,
        description=req.description,
        milestones=req.milestones,
        priority=req.priority,
        domains=req.domains,
    )
    await engine.persist_goals(session, str(user.id))
    return {"status": "ok", "goal": goal.to_dict()}


@router.patch("/goals/{name}")
async def brain_goals_status(
    name: str,
    req: GoalStatusRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Update a goal's status."""
    engine = get_long_term_goals_engine()
    goal = engine.update_goal_status(str(user.id), name, req.status)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal '{name}' not found")
    await engine.persist_goals(session, str(user.id))
    return {"status": "ok", "goal": goal.to_dict()}


@router.post("/goals/{name}/milestones")
async def brain_goals_milestone(
    name: str,
    req: MilestoneRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Complete a milestone for a goal."""
    engine = get_long_term_goals_engine()
    progress = engine.complete_milestone(str(user.id), name, req.milestone)
    if progress is None:
        raise HTTPException(status_code=404, detail=f"Goal '{name}' not found")
    await engine.persist_goals(session, str(user.id))
    return {"status": "ok", **progress.to_dict()}


@router.post("/prioritize")
async def brain_prioritize(
    req: PrioritizeRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Classify tasks by urgency and importance."""
    engine = get_prioritization_engine()
    classified = engine.classify_many(req.tasks, deadlines=req.deadlines)
    return {
        "tasks": [p.to_dict() for p in classified],
        "schedule": engine.schedule(req.tasks),
    }


@router.get("/self-improvement")
async def brain_self_improvement(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return workflow analysis from execution history."""
    engine = get_self_improvement_engine()
    analysis = engine.analyze(str(user.id))
    return {
        "analysis": analysis.to_dict(),
        "recent": engine.recent_records(str(user.id), limit=20),
    }


@router.post("/self-improvement/record")
async def brain_self_improvement_record(
    req: RecordExecutionRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Record an execution outcome for workflow learning."""
    engine = get_self_improvement_engine()
    engine.record(
        str(user.id),
        req.task,
        req.success,
        duration_s=req.duration_s,
        error=req.error,
        strategy=req.strategy,
        domain=req.domain,
    )
    return {"status": "ok", "recorded": True}


# ── Personality ────────────────────────────────────────────────────────


@router.get("/personality")
async def brain_personality(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Return the learned personality profile for the user."""
    engine = PersonalityEngine(session)
    profile = await engine.get_profile(str(user.id))
    return profile.to_dict()


@router.post("/personality/observe")
async def brain_personality_observe(
    query: str,
    response_length: Optional[int] = None,
    feedback: Optional[str] = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Record a personality observation."""
    engine = PersonalityEngine(session)
    await engine.observe(
        str(user.id),
        query,
        response_length=response_length,
        feedback=feedback,
    )
    profile = await engine.get_profile(str(user.id))
    return {"status": "ok", "profile": profile.to_dict()}


# ── Context Engine ─────────────────────────────────────────────────────


@router.get("/context")
async def brain_context(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the current context snapshot for the user."""
    engine = get_context_engine()
    return engine.get_snapshot(str(user.id)).to_dict()


@router.post("/context/update")
async def brain_context_update(
    req: ContextUpdateRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update the context snapshot for the user."""
    engine = get_context_engine()
    uid = str(user.id)
    if req.project:
        engine.set_project(uid, req.project, req.repository or "")
    if req.language:
        engine.set_language(uid, req.language)
    if req.folder:
        engine.set_folder(uid, req.folder)
    if req.file:
        engine.add_recent_file(uid, req.file)
    if req.search:
        engine.add_recent_search(uid, req.search)
    if req.browser_tabs is not None:
        engine.set_browser_tabs(uid, req.browser_tabs)
    if req.running_services is not None:
        engine.set_running_services(uid, req.running_services)
    if req.task:
        engine.set_current_task(uid, req.task)
    return {"status": "ok", "context": engine.get_snapshot(uid).to_dict()}


# ── Continuity ─────────────────────────────────────────────────────────


@router.get("/continuity")
async def brain_continuity(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the continuity state for the user."""
    engine = get_continuity_engine()
    state = engine.restore(str(user.id))
    return {"state": state.to_dict(), "has_state": engine.has_state(str(user.id))}


@router.post("/continuity/snapshot")
async def brain_continuity_snapshot(
    req: ContinuitySnapshotRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Update the continuity snapshot for the user."""
    engine = get_continuity_engine()
    uid = str(user.id)
    engine.snapshot(
        uid,
        conversation_topic=req.conversation_topic,
        open_tasks=req.open_tasks,
        running_workflows=req.running_workflows,
        agent_state=req.agent_state,
        desktop_state=req.desktop_state,
        orb_state=req.orb_state,
        voice_state=req.voice_state,
    )
    return {"status": "ok", "state": engine.get_state(uid).to_dict()}


# ── Self-Monitoring ────────────────────────────────────────────────────


@router.get("/health")
async def brain_health(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Run a health check and return the report."""
    engine = get_self_monitoring_engine()
    report = engine.check()
    return {
        "report": report.to_dict(),
        "recovery_history": engine.recovery_history(limit=10),
    }


@router.post("/health/check")
async def brain_health_check(
    req: HealthCheckRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Run a health check with provided readings."""
    engine = get_self_monitoring_engine()
    report = engine.check(req.readings)
    return {"report": report.to_dict()}


# ── Error Handling ─────────────────────────────────────────────────────


@router.post("/error/explain")
async def brain_error_explain(
    req: ErrorExplainRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Explain an error clearly with recovery steps."""
    engine = get_error_handling_engine()
    explanation = engine.explain(req.error, req.context)
    return {
        "explanation": explanation.to_dict(),
        "message": engine.format_for_user(explanation),
    }


# ── Project Awareness ──────────────────────────────────────────────────


@router.post("/project/scan")
async def brain_project_scan(
    req: ProjectScanRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Scan a project directory and build a profile."""
    engine = get_project_awareness_engine()
    profile = engine.scan(req.root)
    return {"profile": profile.to_dict()}


@router.get("/project/{root:path}")
async def brain_project_get(
    root: str,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a cached project profile or scan it."""
    engine = get_project_awareness_engine()
    profile = engine.get_or_scan(root)
    return {"profile": profile.to_dict()}


# ── Multitasking ───────────────────────────────────────────────────────


@router.post("/multitask/decompose")
async def brain_multitask_decompose(
    req: MultitaskRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Decompose a multi-part request into parallel task specs."""
    engine = get_multitasking_engine()
    tasks = engine.decompose_request(req.request)
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/multitask/history")
async def brain_multitask_history(
    user: User = Depends(get_current_user),
    limit: int = 10,
) -> Dict[str, Any]:
    """Return recent parallel execution results."""
    engine = get_multitasking_engine()
    return {"history": engine.history(limit=limit)}


# ── Productivity ───────────────────────────────────────────────────────


@router.post("/productivity/start")
async def brain_productivity_start(
    req: SessionRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Start a work session."""
    engine = get_productivity_engine()
    session = engine.start_session(str(user.id), task=req.task, category=req.category)
    return {"status": "ok", "session": session.to_dict()}


@router.post("/productivity/end")
async def brain_productivity_end(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """End the active work session."""
    engine = get_productivity_engine()
    session = engine.end_session(str(user.id))
    if session is None:
        return {"status": "no_active_session"}
    return {"status": "ok", "session": session.to_dict()}


@router.get("/productivity/summary")
async def brain_productivity_summary(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the productivity summary for the user."""
    engine = get_productivity_engine()
    uid = str(user.id)
    return {
        "summary": engine.summary(uid).to_dict(),
        "daily": engine.daily_summary(uid),
        "coding": engine.coding_summary(uid),
        "research": engine.research_summary(uid),
    }


# ── Autonomous Improvement ─────────────────────────────────────────────


@router.post("/improvements/detect")
async def brain_improvements_detect(
    req: ImprovementDetectRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Detect optimization opportunities from observations."""
    engine = get_autonomous_improvement_engine()
    opportunities = engine.detect(str(user.id), req.observations)
    return {"opportunities": [o.to_dict() for o in opportunities]}


@router.post("/improvements/apply")
async def brain_improvements_apply(
    req: ImprovementApplyRequest,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Mark an optimization opportunity as applied."""
    engine = get_autonomous_improvement_engine()
    applied = engine.apply(str(user.id), req.description)
    return {"applied": applied, "description": req.description}


@router.get("/improvements")
async def brain_improvements_list(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return pending optimization opportunities."""
    engine = get_autonomous_improvement_engine()
    return {
        "opportunities": [o.to_dict() for o in engine.opportunities(str(user.id))],
        "applied": engine.applied_history(limit=10),
    }