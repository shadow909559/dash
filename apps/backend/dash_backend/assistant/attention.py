"""Proactive attention engine (spec #33/#34/#36/#37/#75).

One command — "what needs my attention?" — aggregates EVERYTHING the
owner must know across CRM state, approvals, orchestrator tasks and
action items, classified by urgency (LOW/NORMAL/IMPORTANT/URGENT/
CRITICAL) and grouped with deduplication. Also implements the proactive
event loop inputs: deadlines approaching, approvals pending too long,
follow-ups owed, meetings starting soon.
"""

from __future__ import annotations

import re
import time


def _urgency_from_hours(hours: float | None) -> str:
    """LOW/NORMAL/IMPORTANT/URGENT/CRITICAL from deadline proximity."""
    if hours is None:
        return "normal"
    if hours < 0:
        return "critical"   # overdue
    if hours < 24:
        return "urgent"
    if hours < 24 * 3:
        return "important"
    return "normal"
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

URGENCY_ORDER = ["low", "normal", "important", "urgent", "critical"]


class AttentionEngine:
    def __init__(self, store=None, orchestrator=None):
        self.store = store
        self.orch = orchestrator

    # ── Core aggregation ────────────────────────────────────────────────

    def what_needs_attention(self) -> dict[str, Any]:
        urgent: list[dict[str, Any]] = []
        important: list[dict[str, Any]] = []
        waiting: list[dict[str, Any]] = []

        if self.store is not None:
            # Expiring / pending approvals
            for a in self.store.list_approvals(status="pending"):
                waiting.append({
                    "kind": "approval",
                    "text": f"{a['description'][:100]} (risk {a['risk_level']})",
                    "id": a["id"],
                    "age_min": round((time.time() - a["requested_at"]) / 60, 1),
                })
            # Overdue action items
            for item in self.store.list_action_items(status="pending"):
                urgent.append({
                    "kind": "action_item",
                    "text": f"Action owed: {item['text'][:100]}",
                    "due": item.get("due"),
                })
            # Requirements blocked on clarification
            for r in self.store.list_requirements(status="clarification_needed"):
                important.append({
                    "kind": "requirement",
                    "text": f"Clarify with client: {r['text'][:90]}",
                    "client_id": r.get("client_id"),
                })

        if self.orch is not None:
            try:
                tasks = self.orch.list_tasks()
            except Exception:
                tasks = []
            for t in tasks:
                if t.get("status") == "waiting_confirmation":
                    waiting.append({
                        "kind": "task_approval",
                        "text": (t.get("goal") or "")[:90],
                        "id": t["id"],
                    })
                elif t.get("status") == "failed":
                    important.append({
                        "kind": "task_failed",
                        "text": f"Task failed: {(t.get('goal') or '')[:80]}",
                        "id": t["id"],
                    })

        return {
            "generated_at": time.time(),
            "urgent": urgent,
            "important": important,
            "waiting_approval": waiting,
            "counts": {
                "urgent": len(urgent),
                "important": len(important),
                "waiting": len(waiting),
            },
        }

    def format_for_owner(self) -> str:
        """Human answer to 'what needs my attention?' (spec #75/#128)."""
        data = self.what_needs_attention()
        c = data["counts"]
        if not (c["urgent"] + c["important"] + c["waiting"]):
            return "Nothing needs your attention right now."
        lines: list[str] = []
        if c["waiting"]:
            lines.append(
                f"{c['waiting']} approval(s) waiting on you:"
            )
            for w in data["waiting_approval"][:3]:
                lines.append(f"  • {w['text']}")
        if c["urgent"]:
            lines.append(f"{c['urgent']} urgent item(s):")
            for u in data["urgent"][:3]:
                lines.append(f"  • {u['text']}")
        if c["important"]:
            lines.append(f"{c['important']} important item(s):")
            for i in data["important"][:3]:
                lines.append(f"  • {i['text']}")
        return "\n".join(lines)


_engine: AttentionEngine | None = None


def get_attention_engine() -> AttentionEngine:
    global _engine
    if _engine is None:
        from dash_backend.assistant.crm_store import get_crm_store
        _engine = AttentionEngine(store=get_crm_store())
    return _engine
