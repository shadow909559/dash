"""Structured CRM store — clients, contacts, projects, requirements,
communications, meetings and action items (decisions.md #92).

DASH's relationship data lives as STRUCTURED records (spec #18/#120), not
free-text memory: every entity is queryable, every requirement has a
lifecycle, every communication has a client boundary. Persistence follows
the repository's established atomic tmp+replace JSON convention (same
pattern as TaskStateStore), so restarts lose nothing and no second
database is introduced.

Storage layout (all under one dir, default app-data):
    crm.json          — versioned document {clients, contacts, projects}
    requirements.json — requirement records keyed by id
    communications.json
    meetings.json
    action_items.json
Each file is independent so a corrupt write cannot wipe every entity.
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

STORE_VERSION = 1

# Requirement lifecycle (spec #22) — deterministic ordering, no free states.
REQUIREMENT_LIFECYCLE = [
    "detected", "clarification_needed", "confirmed", "planned",
    "approved", "in_progress", "implemented", "verified", "delivered",
    "rejected", "dropped",
]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _slug(name: str) -> str:
    """Case/punctuation-insensitive client key so 'acme corp' == 'Acme Corp'."""
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


class _File:
    """One atomic JSON document."""

    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            logger.exception("CRM file unreadable, starting empty: %s", self.path)
            return {}

    def write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)


import json  # noqa: E402  (used by _File; kept next to it for clarity)


class CrmStore:
    """All CRM entities. Synchronous, like TaskStateStore."""
    def __init__(self, base_dir: Path | None = None):
        import os

        base = Path(
            base_dir
            or os.getenv("DASH_CRM_DIR")
            or (Path.home() / ".dash" / "crm")
        )
        self._clients = _File(base / "crm.json")
        self._requirements = _File(base / "requirements.json")
        self._communications = _File(base / "communications.json")
        self._meetings = _File(base / "meetings.json")
        self._action_items = _File(base / "action_items.json")
        self._approvals = _File(base / "approvals.json")
        self._prefs = _File(base / "preferences.json")
        self._decisions = _File(base / "decisions.json")

    # ── Owner preferences (spec #107/#119, decisions.md #95) ──────────

    _PREF_DEFAULTS: dict[str, Any] = {
        "autonomy_mode": "supervised_autonomy",  # manual|assisted|supervised_autonomy|trusted_autonomy
        "global_policy": {"external_messages": "approval"},
        "follow_up_days": 5,          # days of client silence before a follow-up alert
        "proactive_enabled": True,
        "notification_urgency_floor": "important",  # LOW|NORMAL|IMPORTANT|URGENT|CRITICAL
        "quiet_hours": {"start": 0, "end": 0},  # local hours; 0/0 = never quiet (spec #10)
        "retention_days": 90,          # audit/transcript retention; 0 = keep forever (spec #98/#99)
        "working_hours": {"start": 9, "end": 17},   # local hours; business-hours policies
    }

    def get_preferences(self) -> dict[str, Any]:
        data = self._prefs.read()
        stored = data.get("preferences", {})
        merged = dict(self._PREF_DEFAULTS)
        for k, v in stored.items():
            if k in merged:
                merged[k] = v
        merged["updated_at"] = stored.get("updated_at", 0.0)
        return merged

    def update_preferences(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.get_preferences()
        unknown = [k for k in patch if k not in self._PREF_DEFAULTS]
        if unknown:
            raise ValueError(f"unknown preference key(s): {', '.join(sorted(unknown))}")
        mode = patch.get("autonomy_mode", current["autonomy_mode"])
        if mode not in ("manual", "assisted", "supervised_autonomy",
                        "trusted_autonomy"):
            raise ValueError(f"invalid autonomy_mode: {mode}")
        if "follow_up_days" in patch:
            try:
                if not (1 <= int(patch["follow_up_days"]) <= 60):
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError("follow_up_days must be an integer 1-60")
        if "notification_urgency_floor" in patch:
            if patch["notification_urgency_floor"] not in (
                    "low", "normal", "important", "urgent", "critical"):
                raise ValueError("invalid notification_urgency_floor")
        if "quiet_hours" in patch:
            qh = patch["quiet_hours"]
            if not isinstance(qh, dict):
                raise ValueError("quiet_hours must be an object {start, end}")
            try:
                s, e = int(qh.get("start", 0)), int(qh.get("end", 0))
            except (TypeError, ValueError):
                raise ValueError("quiet_hours start/end must be integers 0-23")
            if not (0 <= s <= 23 and 0 <= e <= 23):
                raise ValueError("quiet_hours start/end must be integers 0-23")
        if "retention_days" in patch:
            try:
                if not (0 <= int(patch["retention_days"]) <= 3650):
                    raise ValueError
            except (TypeError, ValueError):
                raise ValueError("retention_days must be an integer 0-3650 (0 = keep forever)")
        data = self._prefs.read()
        stored = data.setdefault("preferences", {})
        for k, v in patch.items():
            if k in self._PREF_DEFAULTS:
                stored[k] = v
        stored["updated_at"] = time.time()
        self._prefs.write(data)
        return self.get_preferences()

    # ── Follow-ups (spec #50, decisions.md #95) ────────────────────────

    def list_follow_ups(self, status: str | None = None) -> list[dict[str, Any]]:
        items = self._prefs.read().get("follow_ups", [])
        if status:
            return [f for f in items if f.get("status") == status]
        return items

    def add_follow_up(self, client_id: str, reason: str,
                      last_communication_id: str | None = None,
                      source: str = "followup_engine") -> dict[str, Any]:
        rec = {
            "id": _new_id("fu"),
            "client_id": client_id,
            "reason": reason[:200],
            "last_communication_id": last_communication_id,
            "source": source,
            "status": "pending",  # pending | sent | dismissed
            "created_at": time.time(),
        }
        data = self._prefs.read()
        data.setdefault("follow_ups", []).append(rec)
        self._prefs.write(data)
        return rec

    def resolve_follow_up(self, follow_up_id: str, status: str) -> bool:
        if status not in ("sent", "dismissed"):
            raise ValueError("follow-up status must be 'sent' or 'dismissed'")
        data = self._prefs.read()
        for f in data.get("follow_ups", []):
            if f.get("id") == follow_up_id:
                f["status"] = status
                f["resolved_at"] = time.time()
                self._prefs.write(data)
                return True
        return False

    def client_timeline(self, client_id: str) -> list[dict[str, Any]]:
        """Unified chronological timeline for one client (spec #105).

        Every entry comes from a real persisted record of this client —
        requirements (with lifecycle history), meetings, communications,
        and follow-ups. Nothing inferred."""
        events: list[dict[str, Any]] = []
        for r in self.list_requirements(client_id=client_id):
            events.append({"ts": r["created_at"], "type": "requirement",
                           "text": r["text"][:120], "status": r["status"],
                           "id": r["id"]})
            for h in r.get("history", []):
                if h.get("status") and h.get("ts"):
                    events.append({"ts": h["ts"], "type": "requirement_status",
                                   "text": f"{r['text'][:80]} → {h['status']}",
                                   "status": h["status"], "id": r["id"]})
        for m in self.list_meetings(client_id=client_id):
            events.append({"ts": m.get("scheduled_at") or m["created_at"],
                           "type": "meeting", "text": m["title"],
                           "status": m.get("status", "scheduled"), "id": m["id"]})
        for c in self.list_communications(client_id=client_id):
            events.append({"ts": c["created_at"],
                           "type": "communication",
                           "text": f"{c['direction']}: {c['summary'][:100]}",
                           "status": "sent" if c.get("sent") else "recorded",
                           "id": c["id"]})
        for f in self.list_follow_ups():
            if f.get("client_id") == client_id:
                events.append({"ts": f["created_at"], "type": "follow_up",
                               "text": f["reason"][:100],
                               "status": f["status"], "id": f["id"]})
        events.sort(key=lambda e: e["ts"] or 0)
        return events

    # ── Clients ────────────────────────────────────────────────────────

    def create_client(
        self, name: str, organization: str = "",
        priority: str = "normal", notes: str = "",
    ) -> dict[str, Any]:
        clients = self._clients.read()
        ckey = _slug(name)
        for c in clients.get("clients", []):
            if c.get("key") == ckey:
                raise ValueError(f"client already exists: {name}")
        client = {
            "id": _new_id("cl"),
            "key": ckey,
            "name": name,
            "organization": organization or name,
            "priority": priority,
            "notes": notes,
            "policy": {
                "external_messages": "approval",  # approval | allow
                "commitments": "approval",
                "auto_answer_calls": False,
            },
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        clients.setdefault("version", STORE_VERSION)
        clients.setdefault("clients", []).append(client)
        clients.setdefault("contacts", [])
        clients.setdefault("projects", [])
        self._clients.write(clients)
        return client

    def get_client(self, name_or_id: str) -> dict[str, Any] | None:
        clients = self._clients.read()
        key = _slug(name_or_id)
        for c in clients.get("clients", []):
            if c.get("id") == name_or_id or c.get("key") == key:
                return c
        return None

    def list_clients(self) -> list[dict[str, Any]]:
        return self._clients.read().get("clients", [])

    def update_client(self, client_id: str, updates: dict[str, Any]) -> bool:
        data = self._clients.read()
        for c in data.get("clients", []):
            if c.get("id") == client_id:
                for k in ("name", "organization", "priority", "notes", "policy"):
                    if k in updates:
                        c[k] = updates[k]
                c["updated_at"] = time.time()
                self._clients.write(data)
                return True
        return False

    # ── Contacts ───────────────────────────────────────────────────────

    def add_contact(
        self, name: str, client_id: str | None = None,
        role: str = "", email: str = "", phone: str = "",
    ) -> dict[str, Any]:
        data = self._clients.read()
        contact = {
            "id": _new_id("ct"),
            "name": name,
            "client_id": client_id,
            "role": role,
            "email": email,
            "phone": phone,
            "trusted": False,
            "created_at": time.time(),
        }
        data.setdefault("contacts", []).append(contact)
        self._clients.write(data)
        return contact

    def list_contacts(self, client_id: str | None = None) -> list[dict[str, Any]]:
        contacts = self._clients.read().get("contacts", [])
        if client_id:
            return [c for c in contacts if c.get("client_id") == client_id]
        return contacts

    # ── Projects ───────────────────────────────────────────────────────

    def create_project(
        self, name: str, client_id: str,
        goals: str = "", deadline: str | None = None,
    ) -> dict[str, Any]:
        data = self._clients.read()
        if not any(c.get("id") == client_id for c in data.get("clients", [])):
            raise ValueError(f"unknown client: {client_id}")
        project = {
            "id": _new_id("pj"),
            "name": name,
            "client_id": client_id,
            "goals": goals,
            "deadline": deadline,
            "status": "active",
            "created_at": time.time(),
        }
        data.setdefault("projects", []).append(project)
        self._clients.write(data)
        return project

    def get_project(self, name_or_id: str) -> dict[str, Any] | None:
        data = self._clients.read()
        low = (name_or_id or "").lower()
        for p in data.get("projects", []):
            if p.get("id") == name_or_id or p.get("name", "").lower() == low:
                return p
        return None

    def list_projects(self, client_id: str | None = None) -> list[dict[str, Any]]:
        projects = self._clients.read().get("projects", [])
        if client_id:
            return [p for p in projects if p.get("client_id") == client_id]
        return projects

    def update_project(self, project_id: str, updates: dict[str, Any]) -> bool:
        data = self._clients.read()
        for p in data.get("projects", []):
            if p.get("id") == project_id:
                for k in ("name", "goals", "deadline", "status", "policy"):
                    if k in updates:
                        p[k] = updates[k]
                p["updated_at"] = time.time()
                self._clients.write(data)
                return True
        return False

    # ── Policy resolution (spec #134/#135/#136) ─────────────────────────

    _POLICY_KEYS = ("external_messages", "schedule_commitments",
                    "meeting_assistant", "auto_follow_ups")

    def effective_policy(self, client_id: str | None = None,
                         project_id: str | None = None) -> dict[str, Any]:
        """Deterministic precedence (spec #136):
        system security > owner global policy > client policy > project
        policy. A lower layer may only TIGHTEN a restriction, never
        loosen one — "allow" under a stricter "approval" above is
        clamped back to the stricter verdict.
        Verdict vocabulary: allow | approval | deny."""
        prefs = self.get_preferences()
        chain: list[tuple[str, dict[str, Any]]] = [
            ("global", dict(prefs.get("global_policy") or {}))]
        client = self.get_client(client_id) if client_id else None
        if client and isinstance(client.get("policy"), dict):
            chain.append(("client", dict(client["policy"])))
        project = self.get_project(project_id) if project_id else None
        if project and isinstance(project.get("policy"), dict):
            chain.append(("project", dict(project["policy"])))
        # "deny" anywhere wins; then "approval"; "allow" only if every
        # layer that speaks to the key allows it.
        result: dict[str, Any] = {}
        for key in self._POLICY_KEYS:
            verdicts = [layer.get(key) for _, layer in chain
                        if layer.get(key) in ("allow", "approval", "deny")]
            if not verdicts:
                result[key] = None
            elif "deny" in verdicts:
                result[key] = "deny"
            elif "approval" in verdicts:
                result[key] = "approval"
            else:
                result[key] = "allow"
            result[f"{key}_sources"] = [
                name for name, layer in chain
                if layer.get(key) in ("allow", "approval", "deny")]
        return result

    # ── Requirements ───────────────────────────────────────────────────

    def add_requirement(
        self, client_id: str, project_id: str | None, text: str,
        status: str = "detected", source: str = "conversation",
        confidence: float = 0.5, category: str = "requirement",
    ) -> dict[str, Any]:
        rec = {
            "id": _new_id("rq"),
            "client_id": client_id,
            "project_id": project_id,
            "text": text,
            "category": category,  # requirement | decision | question | risk | constraint
            "status": status,
            "source": source,
            "confidence": round(float(confidence), 2),
            "history": [{"ts": time.time(), "status": status,
                         "source": source, "confidence": round(float(confidence), 2)}],
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        data = self._requirements.read()
        data.setdefault("version", STORE_VERSION)
        data.setdefault("requirements", []).append(rec)
        self._requirements.write(data)
        return rec

    def update_requirement_status(self, req_id: str, status: str) -> dict[str, Any] | None:
        if status not in REQUIREMENT_LIFECYCLE:
            raise ValueError(f"invalid requirement status: {status}")
        data = self._requirements.read()
        for r in data.get("requirements", []):
            if r.get("id") == req_id:
                r["status"] = status
                r.setdefault("history", []).append(
                    {"ts": time.time(), "status": status, "source": "system"}
                )
                r["updated_at"] = time.time()
                self._requirements.write(data)
                return r
        return None

    def list_requirements(
        self, client_id: str | None = None, project_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        reqs = self._requirements.read().get("requirements", [])
        if client_id:
            reqs = [r for r in reqs if r.get("client_id") == client_id]
        if project_id:
            reqs = [r for r in reqs if r.get("project_id") == project_id]
        if status:
            reqs = [r for r in reqs if r.get("status") == status]
        return reqs

    def get_requirement(self, req_id: str) -> dict[str, Any] | None:
        reqs = self._requirements.read().get("requirements", [])
        for r in reqs:
            if r.get("id") == req_id:
                return r
        return None

    def link_requirement_task(self, req_id: str, task_id: str) -> bool:
        """Record the requirement→task traceability link (#143)."""
        data = self._requirements.read()
        for r in data.get("requirements", []):
            if r.get("id") == req_id:
                links = r.setdefault("task_ids", [])
                if task_id not in links:
                    links.append(task_id)
                    r["updated_at"] = time.time()
                    self._requirements.write(data)
                return True
        return False

    # ── Communications ─────────────────────────────────────────────────

    def record_communication(
        self, client_id: str | None, direction: str, channel: str,
        summary: str, sent: bool, delivery: dict[str, Any] | None = None,
        approval_id: str | None = None,
    ) -> dict[str, Any]:
        rec = {
            "id": _new_id("cm"),
            "client_id": client_id,
            "direction": direction,        # outgoing | incoming | internal
            "channel": channel,            # message | email | call | meeting | note
            "summary": summary[:2000],
            "sent": bool(sent),            # NO FALSE SUCCESS: actual delivery
            "delivery": delivery or {},
            "approval_id": approval_id,
            "created_at": time.time(),
        }
        data = self._communications.read()
        data.setdefault("version", STORE_VERSION)
        data.setdefault("communications", []).append(rec)
        self._communications.write(data)
        return rec

    def list_communications(self, client_id: str | None = None) -> list[dict[str, Any]]:
        comms = self._communications.read().get("communications", [])
        if client_id:
            return [c for c in comms if c.get("client_id") == client_id]
        return comms

    def apply_retention(self, retention_days: int | None = None) -> dict[str, Any]:
        """Owner-configured retention (spec #98/#99, decisions.md #102).

        Deletes only TRANSCRIPT-class content (meeting transcripts,
        communication record summaries) older than ``retention_days``.
        Structural and legal-record content is deliberately preserved:
        client/project/requirement/task records, approvals (authorization
        evidence), and delivery evidence envelopes — the "what happened"
        stays even after the verbatim content expires. days=0 keeps
        everything. Never touches other stores.
        """
        if retention_days is None:
            try:
                retention_days = int(self.get_preferences().get("retention_days", 0))
            except Exception:
                retention_days = 0
        retention_days = max(0, int(retention_days))
        result: dict[str, Any] = {"retention_days": retention_days, "pruned": {}}
        if retention_days <= 0:
            return result
        cutoff = time.time() - retention_days * 86400.0

        # Meeting transcripts: keep the summary + decisions + action-item
        # links, drop verbatim audio-derived content beyond retention.
        data = self._meetings.read()
        changed = False
        for m in data.get("meetings", []):
            transcript = m.get("transcript")
            if transcript and m.get("created_at", 0) < cutoff:
                m["transcript"] = []
                m["transcript_pruned"] = True
                changed = True
        if changed:
            self._meetings.write(data)
        result["pruned"]["meeting_transcripts"] = changed

        # Communication summaries: structural envelope (direction, channel,
        # delivery evidence, approval id) survives; the content drops.
        data = self._communications.read()
        changed = False
        for c in data.get("communications", []):
            if c.get("created_at", 0) < cutoff and c.get("summary"):
                c["summary"] = "[content expired per retention policy]"
                c["content_pruned"] = True
                changed = True
        if changed:
            self._communications.write(data)
        result["pruned"]["communication_content"] = changed
        return result

    # ── Meetings ───────────────────────────────────────────────────────

    def create_meeting(
        self, title: str, client_id: str | None = None,
        project_id: str | None = None, scheduled_at: float | None = None,
    ) -> dict[str, Any]:
        meeting = {
            "id": _new_id("mt"),
            "title": title,
            "client_id": client_id,
            "project_id": project_id,
            "scheduled_at": scheduled_at,
            "status": "scheduled",  # scheduled | live | completed
            "mode": "listen_only",  # listen_only | assisted | authorized_participant
            "transcript": [],
            "summary": None,
            "briefing": None,
            "created_at": time.time(),
        }
        data = self._meetings.read()
        data.setdefault("version", STORE_VERSION)
        data.setdefault("meetings", []).append(meeting)
        self._meetings.write(data)
        return meeting

    def get_meeting(self, meeting_id: str) -> dict[str, Any] | None:
        for m in self._meetings.read().get("meetings", []):
            if m.get("id") == meeting_id:
                return m
        return None

    def update_meeting(self, meeting_id: str, updates: dict[str, Any]) -> bool:
        data = self._meetings.read()
        for m in data.get("meetings", []):
            if m.get("id") == meeting_id:
                m.update(updates)
                self._meetings.write(data)
                return True
        return False

    def list_meetings(
        self, client_id: str | None = None, status: str | None = None,
    ) -> list[dict[str, Any]]:
        meetings = self._meetings.read().get("meetings", [])
        if client_id:
            meetings = [m for m in meetings if m.get("client_id") == client_id]
        if status:
            meetings = [m for m in meetings if m.get("status") == status]
        return meetings

    # ── Approvals (authority engine backing store) ─────────────────────

    def add_approval(self, request: dict[str, Any]) -> None:
        data = self._approvals.read()
        data.setdefault("version", STORE_VERSION)
        data.setdefault("approvals", []).append(request)
        self._approvals.write(data)

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        for a in self._approvals.read().get("approvals", []):
            if a.get("id") == approval_id:
                return a
        return None

    def list_approvals(self, status: str | None = None) -> list[dict[str, Any]]:
        approvals = self._approvals.read().get("approvals", [])
        if status:
            return [a for a in approvals if a.get("status") == status]
        return approvals

    def resolve_approval(
        self, approval_id: str, status: str, by: str = "owner",
        scope: str | None = None, expires_at: float | None = None,
    ) -> bool:
        data = self._approvals.read()
        for a in data.get("approvals", []):
            if a.get("id") == approval_id:
                a["status"] = status
                a["resolved_at"] = time.time()
                a["resolved_by"] = by
                if scope is not None:
                    a["scope"] = scope
                if expires_at is not None:
                    a["expires_at"] = expires_at
                self._approvals.write(data)
                return True
        return False

    # ── Action items ───────────────────────────────────────────────────

    def add_action_item(
        self, text: str, owner: str = "Shadow", due: str | None = None,
        source: str = "meeting", meeting_id: str | None = None,
        client_id: str | None = None,
    ) -> dict[str, Any]:
        rec = {
            "id": _new_id("ai"),
            "text": text,
            "owner": owner,
            "due": due,
            "source": source,
            "meeting_id": meeting_id,
            "client_id": client_id,
            "status": "pending",  # pending | done | cancelled
            "created_at": time.time(),
        }
        data = self._action_items.read()
        data.setdefault("version", STORE_VERSION)
        data.setdefault("action_items", []).append(rec)
        self._action_items.write(data)
        return rec

    def complete_action_item(self, item_id: str) -> bool:
        data = self._action_items.read()
        for a in data.get("action_items", []):
            if a.get("id") == item_id:
                a["status"] = "done"
                self._action_items.write(data)
                return True
        return False

    def list_action_items(self, status: str = "pending") -> list[dict[str, Any]]:
        items = self._action_items.read().get("action_items", [])
        if status:
            return [a for a in items if a.get("status") == status]
        return items


_store: CrmStore | None = None


def get_crm_store() -> CrmStore:
    global _store
    if _store is None:
        _store = CrmStore()
    return _store
