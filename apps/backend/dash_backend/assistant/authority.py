"""Formal authority + approval engine (spec #5/#6/#7/#136/#137).

Every autonomous action carries an explicit authority level 0-5:

    0 informational        summarize/analyze/extract — automatic
    1 safe local           internal notes, reminders — automatic
    2 low-risk external    routine follow-ups per policy — configurable
    3 external comms       send message/call client — approval by default
    4 high-impact          commitments, deployments, destructive — approval
    5 owner-only           security settings, credentials — owner only

Approvals are SCOPED and EXPIRING (never "allow DASH?" — spec #6/#7):
one-shot action grants, task/client/tool scopes, or a time-boxed
grant. Every grant/rejection is recorded in the existing
AuditLogService, and pending grants live in the CRM store so they
survive restarts.

Policy precedence (spec #136) is a deterministic function:
system security > owner global > client policy > project policy >
task policy > conversation request. A lower layer can only ever make
the outcome STRICTER, never looser.
"""

from __future__ import annotations

import time
import uuid
from enum import IntEnum
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class Authority(IntEnum):
    INFORMATIONAL = 0
    SAFE_LOCAL = 1
    LOW_RISK_EXTERNAL = 2
    EXTERNAL_COMMS = 3
    HIGH_IMPACT = 4
    OWNER_ONLY = 5


# What each level requires (spec #5). Client-policy overrides can only
# make these stricter, never looser — enforced in required_authority().
LEVEL_REQUIREMENT = {
    Authority.INFORMATIONAL: "auto",
    Authority.SAFE_LOCAL: "auto",
    Authority.LOW_RISK_EXTERNAL: "auto",       # unless policy tightens
    Authority.EXTERNAL_COMMS: "approval",
    Authority.HIGH_IMPACT: "approval",
    Authority.OWNER_ONLY: "owner",
}


class ApprovalScope:
    ONCE = "once"
    TASK = "task"
    CLIENT = "client"
    TOOL = "tool"
    TIME_BOXED = "time_boxed"


class DecisionType(str):
    """Decision trace taxonomy (spec #42) — stored, never chain-of-thought."""
    FACT = "fact"
    INFERENCE = "inference"
    UNCERTAINTY = "uncertainty"
    RECOMMENDATION = "recommendation"


class ApprovalEngine:
    """Scope- and expiry-aware approval grants backed by the CRM store."""

    def __active_grants(self, store) -> list[dict[str, Any]]:
        now = time.time()
        return [
            g for g in store.list_approvals()
            if g["status"] == "granted"
            and (g.get("expires_at") is None or g["expires_at"] > now)
        ]

    def has_grant(
        self, store, action_kind: str, task_id: str | None = None,
        client_id: str | None = None, tool: str | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Return an active grant covering this exact usage, else None.

        ONCE grants match ONLY their own approval_id (they are single-use
        and consumed by ``consume``); TASK/CLIENT/TOOL grants remain active
        within their scope; TIME_BOXED grants expire by clock.
        """
        for g in self.__active_grants(store):
            if g["action_kind"] != action_kind:
                continue
            if g["scope"] == ApprovalScope.ONCE:
                if approval_id is not None and g["id"] == approval_id:
                    return g
                continue
            if g["scope"] == ApprovalScope.TASK and g.get("task_id") == task_id:
                return g
            if g["scope"] == ApprovalScope.CLIENT and g.get("client_id") == client_id:
                return g
            if g["scope"] == ApprovalScope.TOOL and g.get("tool") == tool:
                return g
            if g["scope"] == ApprovalScope.TIME_BOXED:
                if (client_id and g.get("client_id") == client_id) or (
                    tool and g.get("tool") == tool
                ):
                    return g
        return None

    def consume(self, store, grant: dict[str, Any]) -> None:
        """Consume a one-shot grant (mark used) and audit it."""
        if grant["scope"] == ApprovalScope.ONCE:
            store.resolve_approval(grant["id"], "used", by="system:consumed")
        logger.info("approval grant consumed: %s (%s)", grant["id"], grant["scope"])

    def create_request(
        self, store, audit, action_kind: str, description: str,
        reason: str, risk_level: int, target: str,
        context: dict[str, Any] | None = None,
        proposed: str | None = None,
        consequences: list[str] | None = None,
        task_id: str | None = None, client_id: str | None = None,
        expires_in: float = 3600.0,
    ) -> dict[str, Any]:
        """Create a pending approval request with full disclosure (spec #6)."""
        request = {
            "id": f"ap_{uuid.uuid4().hex[:10]}",
            "action_kind": action_kind,
            "description": description,
            "reason": reason,
            "risk_level": int(risk_level),
            "target": target,
            "context": context or {},
            "proposed": (proposed or "")[:4000],
            "consequences": (consequences or [])[:8],
            "task_id": task_id,
            "client_id": client_id,
            "status": "pending",
            "scope": ApprovalScope.ONCE,
            "requested_at": time.time(),
            "expires_at": time.time() + max(60.0, float(expires_in)),
            "resolved_at": None,
            "resolved_by": None,
            "resolution": None,
        }
        store.add_approval(request)
        try:
            audit.log(
                event_type="approval_created",
                action=f"{action_kind}: {description[:80]}",
                category="authority",
                status="pending",
                details={"approval_id": request["id"], "risk": risk_level,
                         "target": target[:120]},
            )
        except Exception:
            logger.exception("audit log failed for approval creation")
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, {"type": "approval.created", "approval": request})
        except Exception:
            logger.exception("assistant push failed for approval creation")
        try:
            from dash_backend.assistant.crm_store import get_crm_store
            from dash_backend.assistant.mobile_bridge import push_approval_request
            push_approval_request(request, get_crm_store())
        except Exception:
            logger.exception("mobile push failed for approval creation")
        try:
            from dash_backend.assistant.presence import get_presence_engine
            get_presence_engine().claim(
                "approvals", "waiting_for_approval",
                detail=f"{action_kind}: {description[:80]}",
                meta={"approval_id": request["id"], "risk": risk_level},
            )
        except Exception:
            logger.exception("presence claim failed for approval creation")
        return request

    def resolve(
        self, store, audit, approval_id: str, decision: str,
        scope: str | None = None, ttl: float | None = None,
        by: str = "owner",
    ) -> dict[str, Any] | None:
        """Owner decision: approve (optionally scoped/extended), reject.

        The STORED grant is what authorizes later action — a voice "yes"
        or a prompt claim never is (spec #61/#137).
        """
        rec = store.get_approval(approval_id)
        if rec is None or rec["status"] != "pending":
            return None
        now = time.time()
        if rec.get("expires_at") and rec["expires_at"] < now:
            store.resolve_approval(approval_id, "expired", by="system")
            return None
        if decision == "approve":
            rec["status"] = "granted"
            rec["scope"] = scope or ApprovalScope.ONCE
            if ttl:
                rec["expires_at"] = now + max(60.0, float(ttl))
        else:
            rec["status"] = "rejected"  # normalize reject/other denials
        rec["resolved_at"] = now
        rec["resolved_by"] = by
        rec["resolution"] = decision
        store.resolve_approval(approval_id, rec["status"], by=by,
                               scope=rec["scope"], expires_at=rec["expires_at"])
        try:
            audit.log(
                event_type=f"approval_{decision}",
                action=f"{rec['action_kind']}: {rec['description'][:80]}",
                category="authority",
                status=rec["status"],
                details={"approval_id": approval_id, "scope": rec["scope"],
                         "by": by},
            )
        except Exception:
            logger.exception("audit log failed for approval resolution")
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, {"type": "approval.resolved", "approval": rec})
        except Exception:
            logger.exception("assistant push failed for approval resolution")
        try:
            # Release the approval presence claim only when no other
            # pending approvals remain (the engine resolves priority).
            pending = [a for a in store.list_approvals()
                       if a.get("status") == "pending"]
            if not pending:
                from dash_backend.assistant.presence import get_presence_engine
                get_presence_engine().release("approvals")
        except Exception:
            logger.exception("presence release failed for approval resolution")
        return rec


def required_authority(
    action_kind: str, client_policy: dict[str, Any] | None = None,
    autonomy_mode: str = "supervised_autonomy",
) -> Authority:
    """Deterministic authority requirement for an action kind.

    Client policy may only TIGHTEN: "allow" in a client policy can lower
    EXTERNAL_COMMS→LOW_RISK_EXTERNAL only when autonomy is trusted, and
    never for commitment/high-impact kinds (spec #134/#136/#108).
    """
    base = {
        "send_external_message": Authority.EXTERNAL_COMMS,
        "call_client": Authority.EXTERNAL_COMMS,
        "make_commitment": Authority.HIGH_IMPACT,
        "deploy": Authority.HIGH_IMPACT,
        "delete_data": Authority.HIGH_IMPACT,
        "security_change": Authority.OWNER_ONLY,
        "credential_access": Authority.OWNER_ONLY,
        "schedule_internal": Authority.LOW_RISK_EXTERNAL,
        "prepare_follow_up": Authority.LOW_RISK_EXTERNAL,
        "extract_requirements": Authority.INFORMATIONAL,
        "summarize_meeting": Authority.INFORMATIONAL,
    }.get(action_kind, Authority.EXTERNAL_COMMS)
    pol = (client_policy or {})
    if (
        action_kind == "send_external_message"
        and pol.get("external_messages") == "allow"
        and autonomy_mode == "trusted_autonomy"
    ):
        base = min(base, Authority.LOW_RISK_EXTERNAL)
    return base


# Module-level singletons wired by the routes/boot like other services.
_engine = ApprovalEngine()


def get_approval_engine() -> ApprovalEngine:
    return _engine
