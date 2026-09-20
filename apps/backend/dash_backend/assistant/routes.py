"""Assistant REST API (spec #121) — /api/v1/assistant/*.

Convention-faithful: same auth dependency style as task_routes
(get_current_user_id), same HTTPException error semantics.
"""

from __future__ import annotations


from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/assistant")  # namespaced under /api/v1/assistant (decisions.md #92)


# ── Request models ─────────────────────────────────────────────────────

class ClientCreate(BaseModel):
    name: str
    organization: str = ""
    priority: str = "normal"
    notes: str = ""


class ContactCreate(BaseModel):
    name: str
    client_id: str | None = None
    role: str = ""
    email: str = ""
    phone: str = ""


class ProjectCreate(BaseModel):
    name: str
    client_id: str
    goals: str = ""
    deadline: str | None = None


class RequirementCreate(BaseModel):
    client_name: str
    project_name: str | None = None
    text: str
    status: str = "detected"
    confidence: float = 0.5
    category: str = "requirement"


class RequirementStatus(BaseModel):
    status: str


class MeetingCreate(BaseModel):
    title: str
    client_name: str | None = None
    project_name: str | None = None
    scheduled_at: float | None = None


class MeetingMode(BaseModel):
    mode: str  # listen_only | assisted | authorized_participant


class TurnIngest(BaseModel):
    speaker: str
    text: str
    ts: float | None = None


class ApprovalResolve(BaseModel):
    decision: str            # approve | reject
    scope: str | None = None  # once | task | client | tool | time_boxed
    ttl: float | None = None


class MessagePrepare(BaseModel):
    client_name: str
    text: str
    task_id: str | None = None


class SendApproved(BaseModel):
    approval_id: str


# ── Clients / contacts / projects ──────────────────────────────────────

@router.get("/clients")
async def list_clients(user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    return {"clients": get_crm_store().list_clients()}


@router.post("/clients")
async def create_client(req: ClientCreate, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="name must not be empty")
    try:
        client = get_crm_store().create_client(
            req.name.strip(), req.organization, req.priority, req.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return client


@router.get("/clients/{client_name}")
async def get_client(client_name: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client = store.get_client(client_name)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    cid = client["id"]
    return {
        "client": client,
        "contacts": store.list_contacts(client_id=cid),
        "projects": store.list_projects(client_id=cid),
        "requirements": store.list_requirements(client_id=cid),
        "communications": store.list_communications(client_id=cid),
        "meetings": store.list_meetings(client_id=cid),
    }


@router.post("/contacts")
async def add_contact(req: ContactCreate, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    contact = get_crm_store().add_contact(
        req.name, req.client_id, req.role, req.email, req.phone,
    )
    return contact


@router.post("/projects")
async def create_project(req: ProjectCreate, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    try:
        project = get_crm_store().create_project(
            req.name, req.client_id, req.goals, req.deadline,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return project


# ── Client/project policies (spec #134/#135/#136) ───────────────────────

class PolicyPatch(BaseModel):
    client_id: str | None = None
    project_id: str | None = None
    policy: dict  # keys: external_messages, schedule_commitments,
    # meeting_assistant, auto_follow_ups; values: allow|approval|deny


_VALID_VERDICTS = ("allow", "approval", "deny")
_VALID_POLICY_KEYS = ("external_messages", "schedule_commitments",
                      "meeting_assistant", "auto_follow_ups")


@router.put("/policy")
async def set_policy(req: PolicyPatch, user_id: str = Depends(get_current_user_id)):
    """Attach a policy layer to a client or project (spec #134/#135).
    Validated: unknown keys or verdicts are rejected with 422."""
    from dash_backend.assistant.crm_store import get_crm_store
    for k, v in req.policy.items():
        if k not in _VALID_POLICY_KEYS:
            raise HTTPException(status_code=422, detail=f"unknown policy key: {k}")
        if v not in _VALID_VERDICTS:
            raise HTTPException(status_code=422,
                                detail=f"invalid verdict for {k}: {v}")
    store = get_crm_store()
    if req.client_id:
        c = store.get_client(req.client_id)
        if c is None:
            raise HTTPException(status_code=404, detail="unknown client")
        merged = dict(c.get("policy") or {})
        merged.update(req.policy)
        store.update_client(req.client_id, {"policy": merged})
        return {"ok": True, "scope": "client", "policy": merged}
    if req.project_id:
        p = store.get_project(req.project_id)
        if p is None:
            raise HTTPException(status_code=404, detail="unknown project")
        merged = dict(p.get("policy") or {})
        merged.update(req.policy)
        store.update_project(req.project_id, {"policy": merged})
        return {"ok": True, "scope": "project", "policy": merged}
    raise HTTPException(status_code=422, detail="client_id or project_id required")


@router.get("/policy")
async def get_policy(client_id: str | None = None,
                     project_id: str | None = None,
                     user_id: str = Depends(get_current_user_id)):
    """The effective policy after deterministic precedence (spec #136)."""
    from dash_backend.assistant.crm_store import get_crm_store
    return get_crm_store().effective_policy(client_id, project_id)


# ── Presence ──────────────────────────────────────────────────────────

@router.get("/presence")
async def get_presence(user_id: str = Depends(get_current_user_id)):
    """The one authoritative presence snapshot (decisions.md #117).

    Fusion of voice/orchestrator/approval/meeting claims — the frontend
    polls this as the reconciliation fallback for presence.update pushes.
    """
    from dash_backend.assistant.presence import get_presence_engine
    return get_presence_engine().snapshot()


@router.get("/presence/history")
async def get_presence_history(limit: int = 50,
                               user_id: str = Depends(get_current_user_id)):
    """Recent presence transitions, oldest first (decisions.md #123).

    The owner-observable view of the same authoritative engine — lets the
    Assistant Center answer "what has DASH been doing?" from real recorded
    state changes, never fabricated ones.
    """
    from dash_backend.assistant.presence import get_presence_engine
    return get_presence_engine().history(limit)


# ── Requirements ────────────────────────────────────────────────────────

@router.post("/requirements")
async def add_requirement(req: RequirementCreate, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client = store.get_client(req.client_name)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    project = (store.get_project(req.project_name)
               if req.project_name else None)
    rec = store.add_requirement(
        client_id=client["id"], project_id=project["id"] if project else None,
        text=req.text, status=req.status, confidence=req.confidence,
        category=req.category, source="api",
    )
    return rec


@router.get("/requirements")
async def list_requirements(
    client_name: str | None = None, status: str | None = None,
    user_id: str = Depends(get_current_user_id),
):
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client_id = None
    if client_name:
        client = store.get_client(client_name)
        if client is None:
            raise HTTPException(status_code=404, detail="client not found")
        client_id = client["id"]
    return {"requirements": store.list_requirements(client_id=client_id, status=status)}


@router.post("/requirements/{req_id}/status")
async def set_requirement_status(
    req_id: str, req: RequirementStatus,
    user_id: str = Depends(get_current_user_id),
):
    from dash_backend.assistant.crm_store import get_crm_store
    try:
        rec = get_crm_store().update_requirement_status(req_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if rec is None:
        raise HTTPException(status_code=404, detail="requirement not found")
    return rec


# ── Meetings ────────────────────────────────────────────────────────────

@router.post("/meetings")
async def create_meeting(req: MeetingCreate, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client = (store.get_client(req.client_name)
              if req.client_name else None)
    project = (store.get_project(req.project_name)
               if req.project_name else None)
    meeting = store.create_meeting(
        title=req.title,
        client_id=client["id"] if client else None,
        project_id=project["id"] if project else None,
        scheduled_at=req.scheduled_at,
    )
    return meeting


@router.get("/meetings")
async def list_meetings(client: str | None = None,
                        user_id: str = Depends(get_current_user_id)):
    """Meetings on record, optionally scoped to one client (#124)."""
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client_id = None
    if client:
        c = store.get_client(client)
        if c is None:
            raise HTTPException(status_code=404, detail=f"unknown client: {client}")
        client_id = c["id"]
    meetings = store.list_meetings(client_id=client_id)
    return {"meetings": sorted(
        meetings,
        key=lambda m: m.get("scheduled_at") or m.get("created_at") or 0,
        reverse=True) }


@router.get("/meetings/{meeting_id}")
async def get_meeting(meeting_id: str, user_id: str = Depends(get_current_user_id)):
    """Full meeting detail: transcript, summary, mode, briefing (#124)."""
    from dash_backend.assistant.crm_store import get_crm_store
    meeting = get_crm_store().get_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return meeting


@router.post("/meetings/{meeting_id}/briefing")
async def meeting_briefing(meeting_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.meeting_engine import get_meeting_engine
    briefing = get_meeting_engine().prepare_briefing(meeting_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return briefing


@router.post("/meetings/{meeting_id}/start")
async def meeting_start(meeting_id: str, req: MeetingMode, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.meeting_engine import get_meeting_engine
    try:
        meeting = get_meeting_engine().start_live(meeting_id, req.mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if meeting is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return {"ok": True, "mode": req.mode}


@router.post("/meetings/{meeting_id}/turn")
async def meeting_turn(meeting_id: str, req: TurnIngest, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.meeting_engine import get_meeting_engine
    try:
        return get_meeting_engine().ingest_turn(
            meeting_id, req.speaker, req.text, ts=req.ts,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/meetings/{meeting_id}/end")
async def meeting_end(meeting_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.meeting_engine import get_meeting_engine
    summary = get_meeting_engine().end_meeting(meeting_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="meeting not found")
    return summary


# ── Approvals (authority engine) ────────────────────────────────────────

@router.get("/approvals")
async def list_approvals(status: str = "pending", user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    return {"approvals": get_crm_store().list_approvals(status=status)}


@router.post("/approvals/{approval_id}/resolve")
async def resolve_approval(
    approval_id: str, req: ApprovalResolve,
    user_id: str = Depends(get_current_user_id),
):
    from dash_backend.assistant.authority import get_approval_engine
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.services.audit_logs import get_audit_service
    rec = get_approval_engine().resolve(
        get_crm_store(), get_audit_service(),
        approval_id, req.decision, scope=req.scope, ttl=req.ttl,
        by=user_id,
    )
    if rec is None:
        raise HTTPException(
            status_code=409,
            detail="approval not pending (already resolved or expired)",
        )
    return rec


# ── Communications ──────────────────────────────────────────────────────

@router.post("/messages/prepare")
async def prepare_message(req: MessagePrepare, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.communication import get_pipeline
    from dash_backend.assistant.crm_store import get_crm_store
    # The owner's configured autonomy mode governs the authority check
    # (spec #107/#108) — the API never uses a looser hardcoded default.
    mode = get_crm_store().get_preferences().get("autonomy_mode",
                                                 "supervised_autonomy")
    result = await get_pipeline().prepare_message(
        req.client_name, req.text, task_id=req.task_id, user_id=user_id,
        autonomy_mode=mode,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "prepare failed"))
    return result


@router.post("/messages/send-approved")
async def send_approved(req: SendApproved, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.communication import get_pipeline
    result = await get_pipeline().send_approved(req.approval_id, user_id=user_id)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "send failed"))
    return result


@router.get("/communications")
async def list_communications(client_name: str | None = None, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client_id = None
    if client_name:
        client = store.get_client(client_name)
        if client is None:
            raise HTTPException(status_code=404, detail="client not found")
        client_id = client["id"]
    return {"communications": store.list_communications(client_id=client_id)}


# ── Attention ───────────────────────────────────────────────────────────

@router.get("/attention")
async def attention(user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.attention import get_attention_engine
    return get_attention_engine().what_needs_attention()


# ── Owner control plane (spec #109/#142/#77, decisions.md #94) ─────────

class ConvertRequirement(BaseModel):
    pass  # placeholder for future options (e.g. planner model override)


@router.post("/control/stop")
async def control_stop(user_id: str = Depends(get_current_user_id)):
    """Emergency stop: pause autonomous tasks, revoke pending approvals,
    gate outbound sends. Audited."""
    from dash_backend.assistant.control import emergency_stop
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.services.audit_logs import get_audit_service
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    return await emergency_stop(
        get_crm_store(), get_audit_service(), orchestrator=orch, by=user_id,
    )


@router.post("/control/resume")
async def control_resume(user_id: str = Depends(get_current_user_id)):
    """Clear the emergency-stop send gate. Paused tasks stay paused."""
    from dash_backend.assistant.control import resume_from_emergency_stop
    from dash_backend.services.audit_logs import get_audit_service
    return resume_from_emergency_stop(get_audit_service(), by=user_id)


@router.get("/control/status")
async def control_status(user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.control import emergency_stop_status
    return emergency_stop_status()


@router.post("/requirements/{req_id}/convert")
async def convert_requirement(
    req_id: str, user_id: str = Depends(get_current_user_id),
):
    """Requirement → orchestrator task (#142). Only confirmed/approved
    requirements convert; the task passes the orchestrator's normal
    authority gates; the traceability link is stored."""
    from dash_backend.assistant.control import convert_requirement_to_task
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.services.audit_logs import get_audit_service
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    result = await convert_requirement_to_task(
        get_crm_store(), get_audit_service(), req_id,
        user_id=user_id, orchestrator=orch,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=409, detail=result.get("error", "conversion failed"))
    return result


@router.get("/briefing")
async def daily_briefing(user_id: str = Depends(get_current_user_id)):
    """Daily executive brief from real state only (spec #77)."""
    from dash_backend.assistant.control import daily_briefing as _brief
    from dash_backend.assistant.crm_store import get_crm_store
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    return _brief(get_crm_store(), orchestrator=orch)


@router.get("/summary/eod")
async def end_of_day(user_id: str = Depends(get_current_user_id)):
    """End-of-day summary from real records only (spec #78)."""
    from dash_backend.assistant.control import end_of_day_summary
    from dash_backend.assistant.crm_store import get_crm_store
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    return end_of_day_summary(get_crm_store(), orchestrator=orch)


@router.get("/summary/client/{client_name}")
async def client_status(client_name: str, user_id: str = Depends(get_current_user_id)):
    """Grounded client status report (spec #144) — real records only."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.intel import client_status_report
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    report = client_status_report(get_crm_store(), client_name, orchestrator=orch)
    if report is None:
        raise HTTPException(status_code=404, detail=f"unknown client: {client_name}")
    return report


@router.get("/projects/{name_or_id}/health")
async def project_health(name_or_id: str, user_id: str = Depends(get_current_user_id)):
    """Transparent project health indicators (spec #106) — every metric
    derived from actual data, never invented."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.intel import project_health
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    health = project_health(get_crm_store(), name_or_id, orchestrator=orch)
    if health is None:
        raise HTTPException(status_code=404, detail=f"unknown project: {name_or_id}")
    return health


@router.get("/search")
async def search(query: str, client: str | None = None,
                 user_id: str = Depends(get_current_user_id)):
    """Client intelligence search over all real records (spec #103/#104)."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.intel import search_intelligence
    return search_intelligence(get_crm_store(), query, client_name=client)


@router.get("/clients/{client_name}/context")
async def client_context(client_name: str, user_id: str = Depends(get_current_user_id)):
    """Structured context loaded before speaking for/about a client
    (spec #9/#20/#133) — scoped to exactly this client."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.intel import client_context
    ctx = client_context(get_crm_store(), client_name)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"unknown client: {client_name}")
    return ctx


# ── Observability (spec #71/#72/#73/#127/#150) ─────────────────────────

@router.get("/timeline")
async def timeline(client: str | None = None, project: str | None = None,
                   type: str | None = None, status: str | None = None,
                   limit: int = 200,
                   user_id: str = Depends(get_current_user_id)):
    """Unified activity timeline with filters (spec #127)."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.observe import global_timeline
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    return global_timeline(get_crm_store(), orchestrator=orch, client=client,
                           project=project, type_=type, status=status,
                           limit=limit)


@router.get("/tasks/{task_id}/timeline")
async def task_timeline(task_id: str, user_id: str = Depends(get_current_user_id)):
    """Per-task execution timeline (spec #71)."""
    from dash_backend.assistant.observe import task_timeline
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    tl = task_timeline(orch, task_id)
    if tl is None:
        raise HTTPException(status_code=404, detail=f"unknown task: {task_id}")
    return tl


@router.get("/why")
async def why(subject: str, user_id: str = Depends(get_current_user_id)):
    """'Why did you do that?' answered from the operational decision
    record — audit entries + linked records, never hidden reasoning."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.observe import why_did_you
    from dash_backend.services.audit_logs import get_audit_service
    return why_did_you(get_crm_store(), get_audit_service(), subject)


@router.get("/decisions")
async def decisions(limit: int = 50, user_id: str = Depends(get_current_user_id)):
    """Machine-readable decision traces (spec #43) — operational facts
    only: situation, authority, reason, action, result."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.observe import list_decision_traces
    return {"decisions": list_decision_traces(get_crm_store(), limit=limit)}


# ── Calendar bridge (spec #87) ──────────────────────────────────────────

class EventCreate(BaseModel):
    title: str
    start: str
    end: str
    description: str = ""
    attendees: list[str] | None = None
    client_name: str | None = None


@router.get("/calendar/availability")
async def availability(start: str, end: str, duration_minutes: int = 30,
                       user_id: str = Depends(get_current_user_id)):
    """Free/busy windows from the real local calendar (#87)."""
    from dash_backend.assistant.calendar_bridge import find_availability
    return find_availability(start, end, duration_minutes)


@router.post("/calendar/events")
async def create_event(req: EventCreate, user_id: str = Depends(get_current_user_id)):
    """Authority-gated event creation: internal (auto per policy) vs
    attendee event (approval by default) — never bypasses approvals."""
    from dash_backend.assistant.calendar_bridge import schedule_event
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.services.audit_logs import get_audit_service
    store = get_crm_store()
    client_id = None
    if req.client_name:
        c = store.get_client(req.client_name)
        if c is None:
            raise HTTPException(status_code=404, detail=f"unknown client: {req.client_name}")
        client_id = c["id"]
    result = await schedule_event(
        store, get_audit_service(), req.title, req.start, req.end,
        description=req.description, attendees=req.attendees,
        client_id=client_id, user_id=user_id,
    )
    return result


@router.delete("/calendar/events/{event_id}")
async def cancel_event(event_id: str, user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.calendar_bridge import cancel_event
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.services.audit_logs import get_audit_service
    return await cancel_event(get_crm_store(), get_audit_service(), event_id,
                              user_id=user_id)


# ── Latency metrics (spec #45/#114/#115) ────────────────────────────────

@router.get("/metrics")
async def metrics(user_id: str = Depends(get_current_user_id)):
    """Measured latency summaries (avg/median/p95/p99), counters and
    errors. Real samples only — no claimed numbers (spec #114)."""
    from dash_backend.assistant.metrics import summary
    return summary()


@router.get("/capabilities")
async def capabilities(user_id: str = Depends(get_current_user_id)):
    """Degraded-mode capability report (spec #89/#90): every subsystem
    reports operational/degraded/unavailable with its real reason."""
    from dash_backend.assistant.capabilities import capability_status
    return capability_status()


@router.post("/retention/run")
async def run_retention(user_id: str = Depends(get_current_user_id)):
    """Run retention now with the owner-configured retention_days
    (spec #98/#99). Transcript-class content beyond retention is pruned;
    structural + approval + delivery-evidence records always survive."""
    from dash_backend.assistant.crm_store import get_crm_store
    result = get_crm_store().apply_retention()
    try:
        from dash_backend.assistant.push import push_assistant_event
        push_assistant_event(None, {"type": "retention.pruned",
                                    "result": result})
    except Exception:
        pass
    return result


@router.get("/debug")
async def debug(section: str = "all", user_id: str = Depends(get_current_user_id)):
    """Owner debug view (spec #150) — no secrets, no hidden reasoning."""
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.observe import debug_view
    try:
        from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
        orch = get_task_orchestrator()
    except Exception:
        orch = None
    return debug_view(get_crm_store(), orchestrator=orch, section=section)


# ── Owner preferences + follow-ups + timeline (decisions.md #95) ────────

class PreferencesPatch(BaseModel):
    autonomy_mode: str | None = None
    global_policy: dict | None = None
    follow_up_days: int | None = None
    proactive_enabled: bool | None = None
    notification_urgency_floor: str | None = None
    quiet_hours: dict | None = None     # {start,end} local hours; 0/0 = never quiet (spec #10)
    retention_days: int | None = None   # 0 = keep forever; store validates 0-3650
    working_hours: dict | None = None


@router.get("/preferences")
async def get_preferences(user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    return get_crm_store().get_preferences()


@router.put("/preferences")
async def put_preferences(req: PreferencesPatch,
                          user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    patch = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        return get_crm_store().update_preferences(patch)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/follow-ups")
async def list_follow_ups(status: str | None = None,
                          user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    return {"follow_ups": get_crm_store().list_follow_ups(status=status)}


class FollowUpResolve(BaseModel):
    status: str  # sent | dismissed


@router.post("/follow-ups/{follow_up_id}/resolve")
async def resolve_follow_up(follow_up_id: str, req: FollowUpResolve,
                            user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.crm_store import get_crm_store
    try:
        ok = get_crm_store().resolve_follow_up(follow_up_id, req.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not ok:
        raise HTTPException(status_code=404, detail="follow-up not found")
    return {"ok": True}


@router.get("/clients/{client_name}/timeline")
async def client_timeline(client_name: str,
                          user_id: str = Depends(get_current_user_id)):
    """Unified chronological timeline from real records (spec #105)."""
    from dash_backend.assistant.crm_store import get_crm_store
    store = get_crm_store()
    client = store.get_client(client_name)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    return {"client": client["name"],
            "timeline": store.client_timeline(client["id"]) }


# ── Android companion (spec #96, decisions.md #97) ──────────────────────

class CompanionRegister(BaseModel):
    device_id: str
    platform: str = "android"
    token: str = ""


@router.post("/companion/register")
async def companion_register(req: CompanionRegister,
                             user_id: str = Depends(get_current_user_id)):
    """Register a companion device for assistant pushes. The device must
    already hold a valid device token (this route is authenticated) —
    registration only adds it to the push target list."""
    from dash_backend.services.mobile_companion import push_service
    return push_service.register_device(
        device_id=req.device_id, platform=req.platform,
        token=req.token, user_id=user_id,
    )


@router.get("/companion/notifications")
async def companion_notifications(limit: int = 50,
                                  user_id: str = Depends(get_current_user_id)):
    """The companion's fetch path: pushes queued for the phone."""
    from dash_backend.services.mobile_companion import push_service
    return {"notifications": push_service.get_notifications(limit=limit)}


@router.get("/attention/summary")
async def attention_summary(user_id: str = Depends(get_current_user_id)):
    from dash_backend.assistant.attention import get_attention_engine
    return {"summary": get_attention_engine().format_for_owner()}
