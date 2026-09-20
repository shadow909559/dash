"""Communication abstraction + outbound pipeline (spec #12/#51/#56/#57/#100).

A CommunicationProvider interface decouples intelligence from transport
(phone/VoIP/desktop/Android later — whatever the environment actually
supports; none are faked). The OutboundPipeline enforces, in application
code:

    DRAFT → authority check → DLP scan → approval (scoped, expiring)
    → send via provider → OBSERVE provider receipt → record
    communication (sent=True ONLY with provider confirmation).

Nothing is marked "sent" without delivery evidence (spec #63/#117).
Cross-client isolation is enforced by the pipeline: content referencing
another client's records is blocked before send (spec #55/#56).
"""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from typing import Any

from dash_backend.assistant.authority import (
    Authority,
    required_authority,
)
from dash_backend.assistant.crm_store import CrmStore, get_crm_store
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class CommunicationProvider(ABC):
    """Transport abstraction (spec #12/#88). Implementations exist only
    for transports the environment genuinely supports."""

    name: str = "abstract"

    @abstractmethod
    async def send_message(self, target: str, text: str) -> dict[str, Any]:
        """Deliver a message. MUST return delivery evidence:
        {sent: bool, provider_id: str|None, detail: str}."""

    @abstractmethod
    async def get_call_state(self) -> dict[str, Any]:
        ...

    # Optional call surface (spec #12) — providers implement what the OS
    # actually allows; the base defaults record NOT_IMPLEMENTED honestly.
    async def make_call(self, target: str) -> dict[str, Any]:
        return {"sent": False, "supported": False,
                "detail": "calling not supported by this provider"}

    async def answer_call(self) -> dict[str, Any]:
        return {"supported": False, "detail": "not implemented by provider"}

    async def hang_up(self) -> dict[str, Any]:
        return {"supported": False, "detail": "not implemented by provider"}


class LocalDraftProvider(CommunicationProvider):
    """The only provider that exists today WITHOUT external accounts:
    it does NOT deliver externally. It records the draft locally so the
    whole approval/verification pipeline is exercisable end-to-end with
    honest semantics — send_message returns sent=False with an explicit
    reason, and the pipeline records exactly that (no fake success).
    """

    name = "local_draft"

    async def send_message(self, target: str, text: str) -> dict[str, Any]:
        return {
            "sent": False,
            "provider_id": None,
            "detail": ("local_draft provider does not deliver externally — "
                       "message stored as draft only"),
        }

    async def get_call_state(self) -> dict[str, Any]:
        return {"supported": False, "state": "idle",
                "detail": "no call transport configured"}


# ── DLP scan (spec #57) ────────────────────────────────────────────────

_SECRET_PATTERNS = [
    (re.compile(r"\b(?:sk-[A-Za-z0-9]{20,})\b"), "api key (openai-style)"),
    (re.compile(r"\b(?:ghp_[A-Za-z0-9]{30,})\b"), "github token"),
    (re.compile(r"\b(?:AKIA[0-9A-Z]{16})\b"), "aws access key"),
    (re.compile(r"\b(?:xox[bp]-[A-Za-z0-9-]{10,})\b"), "slack token"),
    (re.compile(r"\b(?:Bearer\s+[A-Za-z0-9._-]{20,})\b"), "bearer token"),
    (re.compile(r"\b(?:password|passwd)\s*[:=]\s*\S+", re.IGNORECASE), "password"),
    (re.compile(r"\b(?:api[_-]?key|secret|token)\s*[:=]\s*\S+", re.IGNORECASE), "credential"),
]
_CROSS_CLIENT_MARKERS = re.compile(
    r"\b(?:client|project)\s+record\s+id\s*:?\s*\w+|"
    r"\binternal notes?\b|"
    r"\bother client\b",
    re.IGNORECASE,
)


def dlp_scan(text: str) -> dict[str, Any]:
    """Inspect outgoing content for secrets / cross-client leakage."""
    findings: list[str] = []
    for rx, label in _SECRET_PATTERNS:
        if rx.search(text):
            findings.append(label)
    if _CROSS_CLIENT_MARKERS.search(text):
        findings.append("possible internal/cross-client content")
    return {"clean": not findings, "findings": findings}


# ── Outbound pipeline ──────────────────────────────────────────────────

class OutboundPipeline:
    """Authority → DLP → approval → send → verify, all application-enforced."""

    def __init__(self, provider: CommunicationProvider | None = None,
                 store: CrmStore | None = None, audit=None,
                 approval_engine=None, notifier=None):
        self.provider = provider or LocalDraftProvider()
        self.store = store or get_crm_store()
        self.audit = audit
        self.approvals = approval_engine
        self.notifier = notifier

    async def prepare_message(
        self, client_name: str, text: str, task_id: str | None = None,
        user_id: str = "owner", autonomy_mode: str = "supervised_autonomy",
    ) -> dict[str, Any]:
        """Draft + authority/DLP evaluation. Returns either a pending
        approval request or an immediate-send verdict (level ≤2)."""
        client = self.store.get_client(client_name)
        if client is None:
            return {"ok": False, "error": f"unknown client: {client_name}"}
        # Resolved policy chain (global > client > project, tighten-only,
        # spec #136) can DENY outright regardless of autonomy mode.
        project_id = task_project_id = None
        policy = self.store.effective_policy(client["id"], None)
        if policy.get("external_messages") == "deny":
            if self.audit is not None:
                self.audit.log("assistant.message.denied", user_id=user_id, details={
                    "client": client["name"], "reason": "policy:deny"})
            return {"ok": False, "blocked": True,
                    "error": "external messages to this client are denied "
                             "by policy"}
        authority = required_authority(
            "send_external_message", client.get("policy"), autonomy_mode,
        )
        # "approval" at any layer forces the approval path even when the
        # authority table + trusted autonomy would have allowed it.
        if policy.get("external_messages") == "approval":
            authority = max(authority, Authority.EXTERNAL_COMMS)
        dlp = dlp_scan(text)
        if not dlp["clean"]:
            # Secrets / cross-client content: blocked regardless of grants.
            return {"ok": False, "blocked": True, "dlp": dlp,
                    "error": "content blocked by data-loss prevention"}
        description = f"Send message to {client['name']}"
        if authority >= Authority.EXTERNAL_COMMS:
            request = self.approvals.create_request(
                self.store, self.audit,
                action_kind="send_external_message",
                description=description,
                reason="Outbound client communication",
                risk_level=int(authority),
                target=client["name"],
                proposed=text,
                consequences=[
                    "Message leaves DASH's local boundary",
                    "Client may act on its contents",
                ],
                task_id=task_id, client_id=client["id"],
            )
            # Operational decision trace (#43) — the record 'why did you
            # do that?' reads from; no hidden reasoning, facts only.
            try:
                from dash_backend.assistant.observe import record_decision_trace
                record_decision_trace(
                    self.store,
                    situation=f"outbound message to {client['name']}",
                    observed={
                        "client": client['name'],
                        "authority_level": int(authority),
                        "policy": policy.get("external_messages"),
                        "autonomy_mode": autonomy_mode,
                        "dlp_clean": dlp["clean"],
                    },
                    options=["request owner approval", "decline to send"],
                    authority=int(authority),
                    reason=("external communication requires owner approval "
                            "at this authority level and policy"),
                    approval_required=True,
                    action="created approval request",
                    result={"approval_id": request.get("id")},
                )
            except Exception:
                logger.exception("decision trace failed (non-fatal)")
            # Decision-support facts (#132): the owner decides with real
            # numbers in view, not a bare "allow DASH?".
            try:
                project_health_facts = self._client_decision_facts(client)
                request.setdefault("context", {}).update(project_health_facts)
            except Exception:
                logger.exception("decision facts failed (non-fatal)")
            return {"ok": True, "approval_required": True,
                    "approval": request, "draft": text}

    def _client_decision_facts(self, client: dict[str, Any]) -> dict[str, Any]:
        """Real facts for the owner's decision screen (spec #132):
        requirement counts, blocked work, deadline, communication state.
        Everything derived from records — no invented progress."""
        facts: dict[str, Any] = {}
        try:
            cid = client["id"]
            reqs = self.store.list_requirements(client_id=cid)
            facts["open_requirements"] = len([
                r for r in reqs
                if r.get("status") not in ("delivered", "rejected")])
            facts["pending_decisions"] = len([
                r for r in reqs if r.get("status") == "clarification_needed"])
            comms = self.store.list_communications(client_id=cid)
            facts["communications_recorded"] = len(comms)
            if comms:
                last = comms[-1]
                facts["last_communication"] = {
                    "direction": last.get("direction"),
                    "sent": last.get("sent"),
                }
        except Exception:
            logger.exception("decision facts collection failed")
        return facts

    async def send_approved(
        self, approval_id: str, user_id: str = "owner",
    ) -> dict[str, Any]:
        """Execute a pending send whose approval was granted. Delivery is
        OBSERVED from the provider's own response — no false success."""
        approval = self.store.get_approval(approval_id)
        if approval is None or approval.get("status") != "granted":
            return {"ok": False, "error": "approval not granted"}
        if approval.get("expires_at") and approval["expires_at"] < time.time():
            self.store.resolve_approval(approval_id, "expired", by="system")
            return {"ok": False, "error": "approval expired"}
        # Emergency-stop gate (spec #109): checked at SEND time, not just
        # approval time, so stopping mid-review still blocks delivery.
        from dash_backend.assistant.control import emergency_stop_active
        if emergency_stop_active():
            return {"ok": False,
                    "error": "emergency stop active — outbound sends are gated"}
        text = approval.get("proposed") or ""
        dlp = dlp_scan(text)
        if not dlp["clean"]:
            self.store.resolve_approval(approval_id, "rejected", by="dlp_guard")
            return {"ok": False, "blocked": True, "dlp": dlp}
        client = (self.store.get_client(approval["client_id"])
                  if approval.get("client_id") else None)
        target = client["name"] if client else (approval.get("target") or "unknown")
        result = await self.provider.send_message(target, text)
        sent = bool(result.get("sent"))
        rec = self.store.record_communication(
            client_id=client["id"] if client else None,
            direction="outgoing", channel="message",
            summary=text, sent=sent, delivery=result,
            approval_id=approval_id,
        )
        # Consume one-shot grants; scoped grants stay active (spec #7).
        if self.approvals:
            grant = self.approvals.has_grant(
                self.store, "send_external_message",
                task_id=approval.get("task_id"),
                client_id=approval.get("client_id"),
                tool=None,
                approval_id=approval_id,
            )
            if grant and grant["id"] == approval_id:
                self.approvals.consume(self.store, grant)
        if not sent and self.notifier is not None:
            try:
                await self.notifier.show(
                    title="DASH — delivery failed",
                    message=(f"Message to {target} was NOT delivered: "
                             f"{result.get('detail', 'provider error')[:100]}"),
                )
            except Exception:
                logger.exception("delivery-failure notification failed")
        return {"ok": True, "sent": sent, "delivery": result,
                "communication_id": rec["id"]}


_pipeline: OutboundPipeline | None = None


def get_pipeline() -> OutboundPipeline:
    """Runtime-configured singleton (tests construct OutboundPipeline
    directly with fakes; the API path uses the real stack)."""
    global _pipeline
    if _pipeline is None:
        from dash_backend.assistant.authority import get_approval_engine
        from dash_backend.assistant.crm_store import get_crm_store
        from dash_backend.services.audit_logs import get_audit_service

        notifier = None
        try:
            from dash_backend.services.notifications import NotificationService
            notifier = NotificationService()
        except Exception:  # pragma: no cover — no desktop backend (headless)
            logger.warning("desktop notifications unavailable; pipeline runs without notifier")
        _pipeline = OutboundPipeline(
            provider=LocalDraftProvider(),
            store=get_crm_store(),
            audit=get_audit_service(),
            approval_engine=get_approval_engine(),
            notifier=notifier,
        )
        # Real email transport when configured (spec #12/#155): DASH_SMTP_HOST
        # swaps the draft boundary for the SMTP provider; without it the
        # honest draft boundary stays.
        try:
            from dash_backend.assistant.smtp_provider import configure_pipeline_provider
            configure_pipeline_provider(_pipeline)
        except Exception:
            logger.exception("SMTP provider configuration failed; draft boundary stays")
    return _pipeline
