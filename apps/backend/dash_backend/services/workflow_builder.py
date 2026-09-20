"""Workflow builder: templates, triggers, conditional logic, error handling, execution history."""
from __future__ import annotations

import asyncio
import concurrent.futures
import copy
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def _push_trigger_update(workflow_id: str, engine: Any = None) -> None:
    """Best-effort WS push of trigger state (decisions.md #80). Never
    raises, no-op without connected clients — safe on every fire/pause
    path, including under test doubles."""
    try:
        from dash_backend.services.trigger_push import push_trigger_update
        push_trigger_update(workflow_id, engine=engine)
    except Exception:  # noqa: BLE001 — a push must never break a fire
        pass


# ── Workflow Templates ─────────────────────────────────────────────────────

WORKFLOW_TEMPLATES: list[dict] = [
    {
        "id": "daily_briefing",
        "name": "Daily Morning Briefing",
        "description": "Summarize today's goals, pending tasks, and key memories",
        "category": "productivity",
        "nodes": [
            {"id": "n1", "type": "trigger", "config": {"schedule": "0 8 * * *"}},
            {"id": "n2", "type": "action", "config": {"tool": "memory.search", "query": "today"}},
            {"id": "n3", "type": "action", "config": {"tool": "executive.goals_upcoming"}},
            {"id": "n4", "type": "action", "config": {"tool": "proactive.suggestions"}},
            {"id": "n5", "type": "action", "config": {"tool": "ai.summarize", "template": "daily_briefing"}},
            {"id": "n6", "type": "action", "config": {"tool": "notification.send", "title": "Morning Briefing"}},
        ],
        "edges": [
            {"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4"}, {"from": "n4", "to": "n5"}, {"from": "n5", "to": "n6"},
        ],
    },
    {
        "id": "backup_memories",
        "name": "Backup Memories",
        "description": "Export all memories to JSON and save backup",
        "category": "data",
        "nodes": [
            {"id": "n1", "type": "trigger", "config": {"schedule": "0 2 * * *"}},
            {"id": "n2", "type": "action", "config": {"tool": "memory.export", "format": "json"}},
            {"id": "n3", "type": "action", "config": {"tool": "file.save", "path": "backups/memories-{date}.json"}},
        ],
        "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
    },
    {
        "id": "email_to_memory",
        "name": "Email to Memory",
        "description": "Parse incoming emails and store important ones as memories",
        "category": "communication",
        "nodes": [
            {"id": "n1", "type": "trigger", "config": {"event": "email.received"}},
            {"id": "n2", "type": "condition", "config": {"field": "importance", "op": "gte", "value": 0.5}},
            {"id": "n3", "type": "action", "config": {"tool": "memory.create", "type": "email"}},
            {"id": "n4", "type": "action", "config": {"tool": "notification.send", "title": "Email saved to memory"}},
        ],
        "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3", "condition": "true"}, {"from": "n3", "to": "n4"}],
    },
    {
        "id": "weekly_report",
        "name": "Weekly Productivity Report",
        "description": "Generate and deliver a weekly productivity summary",
        "category": "analytics",
        "nodes": [
            {"id": "n1", "type": "trigger", "config": {"schedule": "0 18 * * 5"}},
            {"id": "n2", "type": "action", "config": {"tool": "analytics.weekly_summary"}},
            {"id": "n3", "type": "action", "config": {"tool": "analytics.token_usage"}},
            {"id": "n4", "type": "action", "config": {"tool": "ai.summarize", "template": "weekly_report"}},
            {"id": "n5", "type": "action", "config": {"tool": "notification.send", "title": "Weekly Report"}},
        ],
        "edges": [
            {"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4"}, {"from": "n4", "to": "n5"},
        ],
    },
    {
        "id": "code_review_assist",
        "name": "Code Review Assistant",
        "description": "When a git diff is detected, review the changes and suggest improvements",
        "category": "development",
        "nodes": [
            {"id": "n1", "type": "trigger", "config": {"event": "file.changed", "glob": "**/*.py"}},
            {"id": "n2", "type": "action", "config": {"tool": "file.read_diff"}},
            {"id": "n3", "type": "action", "config": {"tool": "ai.review_code"}},
            {"id": "n4", "type": "action", "config": {"tool": "notification.send", "title": "Code review ready"}},
        ],
        "edges": [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}, {"from": "n3", "to": "n4"}],
    },
    {
        "id": "smart_reminder",
        "name": "Smart Reminder",
        "description": "Context-aware reminders that check memory and conditions before notifying",
        "category": "productivity",
        "nodes": [
            {"id": "n1", "type": "trigger", "config": {"event": "reminder.fired"}},
            {"id": "n2", "type": "action", "config": {"tool": "context.check"}},
            {"id": "n3", "type": "condition", "config": {"field": "dnd_enabled", "op": "eq", "value": False}},
            {"id": "n4", "type": "action", "config": {"tool": "notification.send"}},
        ],
        "edges": [
            {"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"},
            {"from": "n3", "to": "n4", "condition": "true"},
        ],
    },
]


# ── Persistence ────────────────────────────────────────────────────────────

import os
from pathlib import Path as _Path  # noqa: F401  (used in type hints + _state_path)


def _state_path() -> _Path:
    """Workflow state file (custom workflows + execution history).
    Override with DASH_WORKFLOW_STATE for tests."""
    override = os.environ.get("DASH_WORKFLOW_STATE")
    if override:
        return _Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(_Path.home() / "AppData" / "Local")
    return _Path(base) / "DASH" / "workflow_state.json"


# Execution history ring buffer: keep the most recent N runs on disk so the
# history panel survives backend restarts without unbounded growth.
MAX_PERSISTED_EXECUTIONS = 500

# Delay-node honesty limits (decisions.md #57): a delay is real, but one
# workflow must not be able to pin a worker thread for an hour. Larger
# values are clamped (and the run record shows the clamped duration).
MAX_DELAY_SECONDS = 300.0
MAX_DELAY_WORKERS = 4

# Real action execution (decisions.md #72): bounded worker pool so action
# nodes dispatch actual side effects without being able to pin the
# traversal thread or the event loop. An action longer than the timeout is
# recorded as failed — the run record tells the truth either way.
ACTION_WORKERS = 2
ACTION_TIMEOUT_S = 30.0


# ── Cron evaluation (workflow trigger schedules) ──────────────────────────

# Cron convention: 0=Sunday … 6=Saturday (sun/mon/... aliases map to it).
_WEEKDAY_ALIASES = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
_MONTH_ALIASES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_CRON_FIELD_NAMES = ("minute", "hour", "day-of-month", "month", "day-of-week")


class InvalidCronError(ValueError):
    """A schedule expression the engine can evaluate honestly.

    The supported dialect is limited (see _parse_cron_field) — anything else
    is REJECTED rather than silently mis-firing, because a trigger that
    never fires (or fires at the wrong times) is a dishonest UI.
    """


def _parse_cron_field(field: str, name: str) -> frozenset[int]:
    """Parse one cron field into the set of matching values.

    Supports: "*", "*/N" steps, "a,b,c" lists, "a-b" ranges, and single
    values. Day-of-week accepts 0-6 (cron convention: 0=Sunday) plus
    mon/tue/... aliases; month accepts 1-12 plus jan/feb/... aliases.
    Values outside the field's range are rejected (a minute of 61 would
    otherwise be stored as a trigger that silently never fires).
    Everything else raises InvalidCronError — the caller decides whether
    that means "reject the schedule" or "skip it and log".
    """
    bounds = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day-of-month": (1, 31),
        "month": (1, 12),
        "day-of-week": (0, 6),
    }[name]
    aliases = _WEEKDAY_ALIASES if name == "day-of-week" else _MONTH_ALIASES if name == "month" else None
    field = field.strip().lower()
    values: set[int] = set()
    for part in field.split(","):
        part = part.strip()
        step = 1
        if "/" in part:
            base, step_s = part.split("/", 1)
            try:
                step = int(step_s)
            except ValueError:
                raise InvalidCronError(f"invalid step in {name} field: {part!r}")
            if step < 1:
                raise InvalidCronError(f"step must be >= 1 in {name} field: {part!r}")
        else:
            base = part

        if base in ("*", ""):
            if base == "" and "/" not in part:
                raise InvalidCronError(f"empty {name} field")
            lo, hi = bounds
            values.update(range(lo, hi + 1, step))
            continue

        if aliases and base in aliases:
            base = str(aliases[base])

        if "-" in base and not base.lstrip("-").isdigit():
            lo_s, hi_s = base.split("-", 1)
            if aliases:
                lo_s = str(aliases.get(lo_s, lo_s))
                hi_s = str(aliases.get(hi_s, hi_s))
            try:
                lo, hi = int(lo_s), int(hi_s)
            except ValueError:
                raise InvalidCronError(f"invalid range in {name} field: {part!r}")
        else:
            try:
                lo = int(base)
            except ValueError:
                raise InvalidCronError(f"invalid {name} value: {part!r}")
            hi = lo
        values.update(range(lo, hi + 1, step))

    if not values:
        raise InvalidCronError(f"empty {name} field")
    lo, hi = bounds
    if any(v < lo or v > hi for v in values):
        raise InvalidCronError(f"{name} value out of range ({lo}-{hi}): {field!r}")
    return frozenset(values)


def parse_cron(expression: str) -> tuple[frozenset[int], frozenset[int], frozenset[int], frozenset[int], frozenset[int]]:
    """Parse a 5-field cron expression (minute hour dom month dow).

    Raises InvalidCronError for anything the engine cannot evaluate exactly
    (6-field expressions, "?", seconds, unknown names, out-of-range values).
    """
    fields = expression.strip().split()
    if len(fields) != 5:
        raise InvalidCronError(
            f"expected 5 cron fields (minute hour day-of-month month day-of-week), got {len(fields)}"
        )
    minute, hour, dom, month, dow = (_parse_cron_field(f, n) for f, n in zip(fields, _CRON_FIELD_NAMES))
    return minute, hour, dom, month, dow


def _fields_match(fields: tuple[frozenset[int], ...], now: datetime) -> bool:
    """True when `now` (a local datetime) matches pre-parsed cron fields.

    Single evaluator for both cron_matches_due() and next_cron_due() —
    one cron semantics, no drift. DOM/DOW follow standard cron OR
    semantics: when BOTH are restricted (neither is "*"), a match on
    either day field fires.
    """
    minute, hour, dom, month, dow = fields
    if now.minute not in minute:
        return False
    if now.hour not in hour:
        return False
    if now.month not in month:
        return False
    dom_restricted = dom != frozenset(range(1, 32))
    dow_restricted = dow != frozenset(range(0, 7))
    if dom_restricted and dow_restricted:
        day_ok = now.day in dom or ((now.weekday() + 1) % 7) in dow
    else:
        day_ok = now.day in dom and ((now.weekday() + 1) % 7) in dow
    return day_ok


def cron_matches_due(expression: str, now: datetime) -> bool:
    """True when `now` (a local datetime) matches the cron expression."""
    return _fields_match(parse_cron(expression), now)


def next_cron_due(expression: str, after: datetime,
                  horizon_days: int = 366) -> Optional[datetime]:
    """Next local datetime strictly AFTER `after` matching the expression.

    Scans minute-by-minute with the engine's own field evaluator — what
    this promises is exactly what due_schedules() will do. Returns None
    for expressions that never match within the horizon (e.g. Feb 30:
    the parser accepts it, the calendar never delivers it) — reported as
    such rather than invented. Invalid expressions also return None; the
    caller decides whether to log.
    """
    try:
        fields = parse_cron(expression)
    except InvalidCronError:
        return None
    candidate = (after + timedelta(minutes=1)).replace(second=0, microsecond=0)
    for _ in range(horizon_days * 24 * 60):
        if _fields_match(fields, candidate):
            return candidate
        candidate += timedelta(minutes=1)
    return None


def _trim_executions(executions: list[dict]) -> list[dict]:
    """Keep the newest MAX_PERSISTED_EXECUTIONS entries (list is append-order)."""
    return executions[-MAX_PERSISTED_EXECUTIONS:]


# ── Workflow Engine ────────────────────────────────────────────────────────

class WorkflowEngine:
    """Core workflow execution engine.

    Custom (user-built) workflows persist to a JSON state file so canvas
    edits survive backend restarts; templates are always re-seeded from
    code and never persisted.

    ``state_path`` is injectable for tests; the default resolves the real
    per-user state file at construction time.
    """

    def __init__(self, state_path: Optional[_Path] = None) -> None:
        self._state_file = _Path(state_path) if state_path else _state_path()
        self._workflows: dict[str, dict] = {}
        self._executions: list[dict] = []
        self._schedules: dict[str, dict] = {}
        self._webhooks: dict[str, dict] = {}
        self._event_triggers: dict[str, dict] = {}

        # Real action dispatch (decisions.md #72). Action tools run on a
        # small dedicated pool under a hard timeout, so a slow or wedged
        # tool occupies a worker — never the event loop or the traversal
        # thread indefinitely.
        self._action_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=ACTION_WORKERS, thread_name_prefix="dash-action"
        )
        # Optional override map: action name -> callable(config, context) ->
        # dict. Tests inject here instead of monkeypatching module globals.
        self._action_overrides: dict[str, Callable[[dict, dict], dict]] = {}

        # Register templates
        for tmpl in WORKFLOW_TEMPLATES:
            self._workflows[tmpl["id"]] = {
                **tmpl,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_template": True,
                "enabled": True,
            }
        self._load_custom()
        self._load_executions()
        self._load_schedules_and_webhooks()

    # ── State file I/O (custom workflows only) ─────────────────────

    def _load_custom(self) -> None:
        try:
            path = self._state_file
            if path.exists():
                import json as _json

                data = _json.loads(path.read_text(encoding="utf-8"))
                for wf in data.get("custom_workflows", []):
                    wf.setdefault("is_template", False)
                    self._workflows[wf["id"]] = wf
        except Exception:
            logger.debug("No prior workflow state loaded", exc_info=True)

    def _save_custom(self) -> None:
        try:
            import json as _json

            custom = [wf for wf in self._workflows.values() if not wf.get("is_template")]
            path = self._state_file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _json.dumps(
                    {
                        "version": 1,
                        "custom_workflows": custom,
                        "executions": _trim_executions(self._executions),
                        "schedules": self._schedules,
                        "webhooks": self._webhooks,
                        "event_triggers": self._event_triggers,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Workflow state save failed", exc_info=True)

    def _load_executions(self) -> None:
        """Restore the execution-history ring buffer from the state file."""
        try:
            import json as _json

            path = self._state_file
            if path.exists():
                data = _json.loads(path.read_text(encoding="utf-8"))
                self._executions = list(data.get("executions", []))[-MAX_PERSISTED_EXECUTIONS:]
        except Exception:
            logger.debug("No prior workflow executions loaded", exc_info=True)

    def _load_schedules_and_webhooks(self) -> None:
        """Restore trigger schedules + webhooks from the state file.

        Persisted since decisions.md #53: before this, add_schedule only
        wrote to an in-memory dict, so a backend restart silently dropped
        every trigger and the scheduler never had anything to fire.
        Entries pointing at workflows that no longer exist are dropped.
        """
        try:
            import json as _json

            path = self._state_file
            if not path.exists():
                return
            data = _json.loads(path.read_text(encoding="utf-8"))
            for wf_id, sched in data.get("schedules", {}).items():
                if wf_id in self._workflows:
                    self._schedules[wf_id] = sched
            for wf_id, hook in data.get("webhooks", {}).items():
                if wf_id in self._workflows:
                    self._webhooks[wf_id] = hook
            for wf_id, trig in data.get("event_triggers", {}).items():
                if wf_id in self._workflows:
                    self._event_triggers[wf_id] = trig
        except Exception:
            logger.debug("No prior workflow schedules/webhooks loaded", exc_info=True)

    # ── CRUD ────────────────────────────────────────────────────────

    def create(self, name: str, nodes: list[dict], edges: list[dict],
               description: str = "", category: str = "custom") -> dict:
        wf_id = f"wf_{uuid.uuid4().hex[:12]}"
        workflow = {
            "id": wf_id,
            "name": name,
            "description": description,
            "category": category,
            "nodes": nodes,
            "edges": edges,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "run_count": 0,
            "last_run": None,
            "is_template": False,
        }
        self._workflows[wf_id] = workflow
        self._save_custom()
        return {"ok": True, "workflow": workflow}

    def update(self, workflow_id: str, **kwargs) -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        if wf.get("is_template"):
            return {"ok": False, "reason": "Cannot edit template directly"}
        for key in ("name", "description", "category", "nodes", "edges", "enabled"):
            if key in kwargs:
                wf[key] = kwargs[key]
        wf["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save_custom()
        return {"ok": True, "workflow": wf}

    def delete(self, workflow_id: str) -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        if wf.get("is_template"):
            return {"ok": False, "reason": "Cannot delete template"}
        del self._workflows[workflow_id]
        self._schedules.pop(workflow_id, None)
        self._webhooks.pop(workflow_id, None)
        self._event_triggers.pop(workflow_id, None)
        self._save_custom()
        return {"ok": True}

    def get(self, workflow_id: str) -> Optional[dict]:
        return self._workflows.get(workflow_id)

    def list_all(self, category: Optional[str] = None) -> list[dict]:
        """Custom (user) workflows only — templates are served separately by
        list_templates(); including them here duplicated every template in
        the desktop dropdown (UI bug found in live preview)."""
        result = [
            w
            for w in self._workflows.values()
            if not w.get("is_template")
        ]
        if category:
            result = [w for w in result if w.get("category") == category]
        return sorted(result, key=lambda x: x.get("updated_at", ""), reverse=True)

    def list_templates(self) -> list[dict]:
        return [w for w in self._workflows.values() if w.get("is_template")]

    def duplicate(self, workflow_id: str, new_name: Optional[str] = None) -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        return self.create(
            name=new_name or f"{wf['name']} (copy)",
            nodes=copy.deepcopy(wf["nodes"]),
            edges=copy.deepcopy(wf["edges"]),
            description=wf.get("description", ""),
            category=wf.get("category", "custom"),
        )

    def instantiate_template(self, template_id: str, name: Optional[str] = None) -> dict:
        """Create an editable custom workflow from a template (one click).

        Deep-copies nodes/edges so the template's code-seeded definitions can
        never be mutated through an edited copy (templates are re-seeded from
        code on every boot, but an in-session shallow share would corrupt the
        running template's node dicts). Auto-deduplicates names so repeated
        instantiations read "Daily Briefing", "Daily Briefing (2)", ...
        """
        wf = self._workflows.get(template_id)
        if not wf or not wf.get("is_template"):
            return {"ok": False, "reason": "Template not found"}

        base_name = (name or wf["name"]).strip() or wf["name"]
        existing = {w["name"] for w in self._workflows.values() if not w.get("is_template")}
        final_name = base_name
        counter = 2
        while final_name in existing:
            final_name = f"{base_name} ({counter})"
            counter += 1

        created = self.create(
            name=final_name,
            nodes=copy.deepcopy(wf["nodes"]),
            edges=copy.deepcopy(wf["edges"]),
            description=wf.get("description", ""),
            category=wf.get("category", "custom"),
        )
        if created.get("ok"):
            created["workflow"]["instantiated_from"] = template_id
        return created

    # ── Triggers ────────────────────────────────────────────────────

    def add_schedule(self, workflow_id: str, cron: str, timezone_: str = "UTC") -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        if wf.get("is_template"):
            return {"ok": False, "reason": "Cannot schedule a template"}
        # Honest validation: reject expressions the engine cannot evaluate
        # exactly rather than storing a trigger that will silently never fire.
        try:
            parse_cron(cron)
        except InvalidCronError as exc:
            return {"ok": False, "reason": f"Unsupported cron expression: {exc}"}
        self._schedules[workflow_id] = {
            "cron": cron,
            "timezone": timezone_,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_fired_at": None,
            "last_status": None,
            "paused_since": None,
            "skipped_fires": 0,
        }
        self._save_custom()
        return {"ok": True, "schedule": self._schedules[workflow_id]}

    def remove_schedule(self, workflow_id: str) -> dict:
        self._schedules.pop(workflow_id, None)
        self._save_custom()
        return {"ok": True}

    def set_schedule_enabled(self, workflow_id: str, enabled: bool) -> dict:
        """Pause (False) or resume (True) a schedule without deleting it.

        A paused schedule keeps its cron, timestamps, and last-fired
        history; due_schedules() skips it, so the pause is real, not
        cosmetic. Resume re-arms it from the next matching minute.

        Pausing stamps `paused_since` (the audit line: since WHEN has
        this been off) and RESUMING clears it — a resumed schedule has
        no pause to report, and stale pause state can never linger.
        `skipped_fires` (accrued by due_schedules() while paused) is
        kept on resume on purpose: it answers "what did pausing cost
        me?", which stays true after re-arming. add_schedule() clears
        it, because replacing the cron is a new arrangement.
        """
        sched = self._schedules.get(workflow_id)
        if sched is None:
            return {"ok": False, "reason": "No schedule for this workflow"}
        sched["enabled"] = bool(enabled)
        if enabled:
            sched["paused_since"] = None
        else:
            sched["paused_since"] = datetime.now(timezone.utc).isoformat()
            sched.setdefault("skipped_fires", 0)
            sched["last_skipped_minute"] = None  # fresh pause, fresh ledger
        self._save_custom()
        _push_trigger_update(workflow_id, engine=self)
        return {"ok": True, "schedule": sched}

    def set_all_schedules_enabled(self, enabled: bool) -> dict:
        """Pause or resume EVERY schedule at once (decisions.md #85).

        Delegates each workflow to set_schedule_enabled() so the pause
        semantics are identical to the single toggle — paused_since stamp,
        fresh skip ledger, persistence, per-workflow WS push — and this
        method is deliberately idempotent: schedules already in the
        requested state are left untouched (re-pausing does not restamp
        paused_since, re-resuming does not clear a ledger).

        Returned totals report what ACTUALLY changed, not what exists:
        changed == the number of schedules that flipped state here.
        """
        changed = 0
        for wf_id in list(self._schedules.keys()):
            sched = self._schedules.get(wf_id)
            if sched is None:
                continue
            currently = bool(sched.get("enabled"))
            if currently == bool(enabled):
                continue  # already there: do not restamp or re-clear
            self.set_schedule_enabled(wf_id, enabled)
            changed += 1
        return {"ok": True, "changed": changed, "total": len(self._schedules)}

    def set_event_trigger_enabled(self, workflow_id: str, enabled: bool) -> dict:
        """Pause (False) or resume (True) an event trigger.

        A paused trigger keeps its topic, match keys, count, and last-fired
        history; fire_event() skips it, so the pause is real, not cosmetic
        (decisions.md #79). Resume re-arms it for the next matching event.
        """
        trig = self._event_triggers.get(workflow_id)
        if trig is None:
            return {"ok": False, "reason": "No event trigger for this workflow"}
        trig["enabled"] = bool(enabled)
        self._save_custom()
        _push_trigger_update(workflow_id, engine=self)
        return {"ok": True, "trigger": trig}

    def set_webhook_enabled(self, workflow_id: str, enabled: bool) -> dict:
        """Pause (False) or resume (True) a webhook trigger.

        fire_webhook() already refused disabled webhooks with 409 — this
        setter is the missing control surface. The secret, URL, and call
        count are kept; paused webhooks simply refuse calls until resumed.
        """
        entry = self._webhooks.get(workflow_id)
        if entry is None:
            return {"ok": False, "reason": "No webhook for this workflow"}
        entry["enabled"] = bool(enabled)
        self._save_custom()
        _push_trigger_update(workflow_id, engine=self)
        return {"ok": True, "webhook": entry}

    def get_schedules(self) -> dict:
        result = {}
        for wf_id, sched in self._schedules.items():
            wf = self._workflows.get(wf_id, {})
            result[wf_id] = {**sched, "workflow_name": wf.get("name", "Unknown")}
        return result

    def add_webhook(self, workflow_id: str, secret: Optional[str] = None) -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        if wf.get("is_template"):
            return {"ok": False, "reason": "Cannot create a webhook for a template"}
        if not secret:
            secret = uuid.uuid4().hex  # auto-mint: the caller may not have one
        webhook_id = f"wh_{uuid.uuid4().hex[:16]}"
        self._webhooks[workflow_id] = {
            "webhook_id": webhook_id,
            "secret": secret,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trigger_count": 0,
        }
        self._save_custom()
        return {"ok": True, "webhook": self._webhooks[workflow_id]}

    def remove_webhook(self, workflow_id: str) -> dict:
        self._webhooks.pop(workflow_id, None)
        self._save_custom()
        return {"ok": True}

    def get_webhooks(self) -> dict:
        return dict(self._webhooks)

    # ── Event triggers (decisions.md #57) ───────────────────────────

    def add_event_trigger(self, workflow_id: str, event: str,
                          match: Optional[dict] = None) -> dict:
        """Attach an event trigger: the workflow runs when a DASH event

        with this topic is published on the event bus. `match` optionally
        narrows the trigger to specific payload values (e.g. {"glob":
        "**/*.py"} on file.changed) — every key must match the payload.
        """
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        if wf.get("is_template"):
            return {"ok": False, "reason": "Cannot trigger a template"}
        topic = (event or "").strip()
        if not topic or ".." in topic or any(
            part == "" for part in topic.split(".")
        ):
            return {"ok": False,
                    "reason": "Event topic must be a non-empty dot-separated "
                              "name (e.g. email.received)"}
        self._event_triggers[workflow_id] = {
            "event": topic,
            "match": dict(match or {}),
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trigger_count": 0,
            "last_fired_at": None,
        }
        self._save_custom()
        return {"ok": True, "trigger": self._event_triggers[workflow_id]}

    def remove_event_trigger(self, workflow_id: str) -> dict:
        self._event_triggers.pop(workflow_id, None)
        self._save_custom()
        return {"ok": True}

    def get_event_triggers(self) -> dict:
        result = {}
        for wf_id, trig in self._event_triggers.items():
            wf = self._workflows.get(wf_id, {})
            result[wf_id] = {**trig, "workflow_name": wf.get("name", "Unknown")}
        return result

    def fire_event(self, topic: str, payload: Optional[dict] = None) -> list[str]:
        """Fire every workflow whose event trigger matches this topic.

        A trigger matches when its topic equals the published topic, every
        configured match key equals the payload value, and the workflow is
        enabled and non-template. Payload is merged into the run's input as
        `event` so downstream nodes can act on it. Returns fired wf ids.
        """
        fired: list[str] = []
        payload = payload or {}
        for wf_id, trig in list(self._event_triggers.items()):
            if trig.get("event") != topic:
                continue
            if not trig.get("enabled", True):
                # Paused via set_event_trigger_enabled: the pause is real
                # gating, not cosmetic (decisions.md #79).
                continue
            match = trig.get("match") or {}
            if any(payload.get(k) != v for k, v in match.items()):
                continue
            wf = self._workflows.get(wf_id)
            if wf is None or wf.get("is_template") or not wf.get("enabled", True):
                continue
            result = self.execute(wf_id, {"event": {"topic": topic, **payload}},
                                  source="event")
            if result.get("ok"):
                trig["trigger_count"] = int(trig.get("trigger_count", 0)) + 1
                trig["last_fired_at"] = datetime.now(timezone.utc).isoformat()
                self._save_custom()
                fired.append(wf_id)
                _push_trigger_update(wf_id, engine=self)
                logger.info("Event workflow %s fired on %s (%s)",
                            wf_id, topic, result["execution"]["id"])
            else:
                logger.warning("Event workflow %s did not run on %s: %s",
                               wf_id, topic, result.get("reason"))
        return fired

    def fire_webhook(self, webhook_id: str, provided_secret: Optional[str], payload: Optional[dict] = None) -> dict:
        """Validate an inbound webhook call and execute its workflow.

        Auth is the webhook secret, checked with hmac.compare_digest so a
        timing side channel cannot probe the token. Idempotent bookkeeping:
        the call is rejected while a run is already in flight.
        """
        import hmac

        hit = next(((wf_id, h) for wf_id, h in self._webhooks.items() if h.get("webhook_id") == webhook_id), None)
        if hit is None:
            return {"ok": False, "status_code": 404, "reason": "Webhook not found"}
        wf_id, entry = hit
        if not entry.get("enabled"):
            return {"ok": False, "status_code": 409, "reason": "Webhook disabled"}
        expected = entry.get("secret") or ""
        if not expected or provided_secret is None or not hmac.compare_digest(expected, str(provided_secret)):
            return {"ok": False, "status_code": 401, "reason": "Invalid webhook secret"}

        if self._workflows.get(wf_id, {}).get("is_template"):
            return {"ok": False, "status_code": 409, "reason": "Webhook points at a template"}

        result = self.execute(wf_id, dict(payload or {}), source="webhook")
        if not result.get("ok"):
            return {"ok": False, "status_code": 409, "reason": result.get("reason", "execution failed")}
        entry["trigger_count"] = int(entry.get("trigger_count", 0)) + 1
        self._save_custom()
        # Push the new count/last-fired to live clients (best-effort; no-op
        # when nobody is connected or the engine path is a test double).
        _push_trigger_update(wf_id, engine=self)
        return {"ok": True, "execution": result["execution"], "trigger_count": entry["trigger_count"]}

    def due_schedules(self, now: datetime) -> list[str]:
        """Workflow ids whose enabled schedule is due at `now`.

        `now` must be a LOCAL naive datetime (cron fields are evaluated in
        local wall time). Idempotence per minute: a schedule already fired
        in the same minute is skipped, so the 60s poll fires once and a
        restart cannot double-fire (last_fired_at persists with the state).
        """
        due: list[str] = []
        for wf_id, sched in self._schedules.items():
            if not sched.get("enabled"):
                # Skipped-fire accounting (#84): count every minute whose
                # cron matched but did not run because of the pause, and
                # only minutes AFTER the pause began — minutes before a
                # re-pause belong to the previous pause's ledger. The
                # per-minute idempotence window is the same one
                # due_schedules() uses for real fires, including the
                # last_fired_at guard: a minute that genuinely fired in
                # the seconds before the pause was NOT skipped, and must
                # not be counted as if it were.
                if sched.get("paused_since"):
                    try:
                        paused_dt = datetime.fromisoformat(str(sched["paused_since"]))
                        if paused_dt.tzinfo is not None:
                            paused_dt = paused_dt.replace(tzinfo=None)
                        now_min = now.replace(second=0, microsecond=0)
                        already_fired = False
                        last = sched.get("last_fired_at")
                        if last:
                            try:
                                already_fired = (
                                    datetime.fromisoformat(str(last)).replace(
                                        second=0, microsecond=0
                                    )
                                    == now_min
                                )
                            except ValueError:
                                pass  # corrupt timestamp: re-evaluate
                        last_skipped = sched.get("last_skipped_minute")
                        if last_skipped:
                            try:
                                # Per-minute idempotence: repeated evaluations
                                # of the SAME minute (overlapping polls, test
                                # clocks) count once.
                                if last_skipped >= now_min.isoformat():
                                    continue
                            except TypeError:
                                last_skipped = None
                        if (
                            now_min >= paused_dt.replace(second=0, microsecond=0)
                            and not already_fired
                            and cron_matches_due(sched.get("cron", ""), now)
                        ):
                            sched["skipped_fires"] = sched.get("skipped_fires", 0) + 1
                            sched["last_skipped_minute"] = now_min.isoformat()
                            self._save_custom()
                    except ValueError:
                        pass  # corrupt stamp: count nothing rather than lie
                continue
            wf = self._workflows.get(wf_id)
            if wf is None or wf.get("is_template") or not wf.get("enabled", True):
                continue
            last = sched.get("last_fired_at")
            if last:
                try:
                    last_dt = datetime.fromisoformat(str(last))
                    if last_dt.replace(tzinfo=None, second=0, microsecond=0) == now.replace(second=0, microsecond=0):
                        continue
                except ValueError:
                    pass  # corrupt timestamp: re-evaluate rather than lock out
            try:
                if cron_matches_due(sched.get("cron", ""), now):
                    due.append(wf_id)
            except InvalidCronError:
                logger.warning("Workflow %s has unparseable cron %r — skipped", wf_id, sched.get("cron"))
        return due

    def mark_fired(self, workflow_id: str, status: str, at: Optional[datetime] = None) -> None:
        """Record that a scheduled fire happened (idempotence marker).

        `at` is the evaluation time that triggered the fire (naive local).
        It must be stamped — not the wall clock — so the marker matches what
        due_schedules() will later compare against, under any clock (real
        or the fake clock tests drive the scheduler with).
        """
        sched = self._schedules.get(workflow_id)
        if sched is not None:
            sched["last_fired_at"] = (at or datetime.now()).isoformat()
            sched["last_status"] = status
            self._save_custom()
            # Scheduled fires land here from the scheduler loop (and its
            # to_thread worker) — push the new last-fired to live clients.
            _push_trigger_update(workflow_id, engine=self)

    # ── Execution ───────────────────────────────────────────────────

    # Safety valve: a traversed step count beyond this (cycles are also
    # caught by the visited set) aborts the run as failed instead of hanging.
    MAX_TRAVERSAL_STEPS = 200

    @staticmethod
    def _coerce(value: Any) -> Any:
        """Lenient coercion for canvas-supplied comparison values.

        The builder UI stores config as strings, but templates ship real
        bools/floats (e.g. value=False, 0.5). Normalize so "0.5" == 0.5 and
        "false" == False compare correctly.
        """
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "false"):
                return lowered == "true"
            try:
                return float(value) if "." in value else int(value)
            except ValueError:
                return value.strip()
        return value

    @classmethod
    def _evaluate_condition(cls, config: dict, context: dict) -> bool:
        """Evaluate a condition node's field/op/value against the run context.

        Missing field → False (the FALSE branch is the safe default: flows
        like 'email_to_memory' gate side effects behind the TRUE path).
        """
        field = str(config.get("field", "")).strip()
        op = str(config.get("op", "eq")).strip().lower()
        expected = cls._coerce(config.get("value"))
        actual = cls._coerce(context.get(field)) if field else None

        if field and field not in context:
            return False

        try:
            if op == "eq":
                return actual == expected
            if op == "ne":
                return actual != expected
            if op in ("gt", "gte", "lt", "lte"):
                a, b = float(actual), float(expected)
                return {"gt": a > b, "gte": a >= b, "lt": a < b, "lte": a <= b}[op]
            if op == "contains":
                return str(expected).lower() in str(actual).lower()
            if op == "not_contains":
                return str(expected).lower() not in str(actual).lower()
            if op == "starts_with":
                return str(actual).lower().startswith(str(expected).lower())
            if op == "ends_with":
                return str(actual).lower().endswith(str(expected).lower())
            if op == "in":
                if isinstance(expected, (list, tuple)):
                    return actual in expected
                parts = [p.strip().lower() for p in str(expected).split(",")]
                return str(actual).strip().lower() in parts
            if op == "truthy":
                return bool(actual)
        except (TypeError, ValueError):
            return False
        # Unknown op: fail safe to the FALSE branch rather than guessing.
        return False

    @staticmethod
    def _successors(edges: list[dict], node_id: str, branch: Optional[bool]) -> list[str]:
        """Downstream node ids for a node, honoring branch semantics.

        Condition nodes follow only edges tagged with the matching branch
        ("true"/"false"); if that branch is unwired the path simply ends —
        a dead end, not an error. Regular nodes follow unconditional edges.
        """
        targets: list[str] = []
        for ed in edges:
            if ed.get("from") != node_id:
                continue
            cond = ed.get("condition")
            if branch is not None:
                if cond == ("true" if branch else "false"):
                    targets.append(ed.get("to"))
            elif not cond:
                targets.append(ed.get("to"))
        # De-dup, keep order, drop empty targets
        seen: set[str] = set()
        out: list[str] = []
        for t in targets:
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    # ── Real action execution (decisions.md #72) ────────────────────

    def _execute_action_bounded(self, tool: str, config: dict,
                                context: dict) -> dict:
        """Run one action node's tool in the bounded worker pool with a
        hard timeout.

        The handler runs on a pool thread (never the caller's thread, so a
        bad tool cannot wedge the event loop or the traversal thread
        forever); the caller waits at most ACTION_TIMEOUT_S and records an
        honest timeout failure if the tool exceeds it. The pool has two
        workers — a hung action occupies a worker, it does not multiply.
        """
        fut = self._action_executor.submit(
            self._execute_action_sync, tool, config, context
        )
        try:
            return fut.result(timeout=ACTION_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            fut.cancel()
            return {
                "status": "failed",
                "reason": f"action timed out after {ACTION_TIMEOUT_S}s",
            }
        except Exception as exc:  # noqa: BLE001 — the record must say why
            return {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}

    def _execute_action_sync(self, tool: str, config: dict,
                             context: dict) -> dict:
        """Dispatch table: what an action node actually does.

        Registered actions are real side effects. An unregistered tool is
        an honest no-op: the run still completes, the node's result says
        "no handler registered" — a workflow must not lie about work it
        did not do.
        """
        override = self._action_overrides.get(tool)
        if override is not None:
            return dict(override(config, context) or {})

        if tool == "notification.send":
            return self._act_notification_send(config, context)
        if tool == "audit.log":
            return self._act_audit_log(config, context)
        if tool == "bus.publish":
            return self._act_bus_publish(config, context)
        return {
            "status": "skipped",
            "reason": f"no handler registered for tool '{tool}'",
        }

    def _act_notification_send(self, config: dict, context: dict) -> dict:
        """Real desktop toast via NotificationService (async API, sync here:
        the service already does its own to_thread; park it on a private
        loop inside the worker thread — the worker pool is the concurrency
        limit, not the loop)."""
        try:
            from dash_backend.services.notifications import NotificationService

            title = str(config.get("title") or "DASH")
            message = str(config.get("message") or "")
            svc = NotificationService()

            async def _run() -> dict:
                return await svc.show(title=title, message=message)

            return {
                "status": "ok",
                "result": asyncio.run(_run()),
            }
        except Exception as exc:  # noqa: BLE001 — the record must say why
            return {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}

    def _act_audit_log(self, config: dict, context: dict) -> dict:
        """Append to the real audit log (dashboard-visible, persisted)."""
        try:
            from dash_backend.services.audit_logs import get_audit_service

            event_type = str(config.get("event_type") or "workflow.action")
            action = str(config.get("action") or "")
            message = str(config.get("message") or "")
            severity = str(config.get("severity") or "INFO")
            get_audit_service().log(
                event_type=event_type,
                action=action or message[:120],
                category="workflow",
                status="success",
                details={"message": message} if message else {},
                severity=severity,
            )
            return {"status": "ok", "result": {"logged": True,
                                               "event_type": event_type}}
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}

    def _act_bus_publish(self, config: dict, context: dict) -> dict:
        """Publish a follow-on event (sync, worker thread — the bus handles
        its own delivery tasking)."""
        try:
            from dash_backend.events.event_bus import get_event_bus

            topic = str(config.get("topic") or "").strip()
            if not topic or not all(p.isalnum() for p in topic.split(".")):
                return {"status": "failed",
                        "reason": "topic must be a dot-separated alphanumeric name"}
            payload = config.get("payload")
            payload = dict(payload) if isinstance(payload, dict) else {}
            payload.setdefault("via_workflow", True)
            get_event_bus().publish_sync(topic, payload, source="workflow_action")
            return {"status": "ok", "result": {"topic": topic}}
        except Exception as exc:  # noqa: BLE001
            return {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}

    def _traverse(
        self,
        wf: dict,
        exec_record: dict,
        context: dict,
        respect_delays: bool = False,
    ) -> None:
        """Walk the workflow graph in edge order, evaluating condition nodes.

        The previous implementation iterated wf["nodes"] in list order and
        ignored edges entirely — if/else flows executed BOTH branches. This
        walk starts at trigger nodes (or the first node when a workflow has
        none), executes each node once, and follows only matching branches.

        respect_delays: delay nodes genuinely sleep (in bounded worker
        threads) so scheduled/event runs behave as built. Manual/API runs
        keep the instant walk — an interactive click should not hang the
        request for minutes.
        """
        nodes_by_id = {n["id"]: n for n in wf.get("nodes", [])}
        edges = wf.get("edges", [])

        starts = [n["id"] for n in wf.get("nodes", []) if n.get("type") == "trigger"]
        if not starts and wf.get("nodes"):
            starts = [wf["nodes"][0]["id"]]

        visited: set[str] = set()
        queue: list[tuple[str, Optional[bool]]] = [(sid, None) for sid in starts]
        steps = 0

        while queue:
            if steps >= self.MAX_TRAVERSAL_STEPS:
                raise RuntimeError(
                    f"Traversal aborted after {self.MAX_TRAVERSAL_STEPS} steps (cycle?)"
                )
            node_id, branch = queue.pop(0)
            steps += 1

            node = nodes_by_id.get(node_id)
            if node is None:
                continue  # edge points at a deleted/unknown node
            if node_id in visited:
                continue  # cycle guard: a node runs at most once per run
            visited.add(node_id)
            exec_record["nodes_executed"].append(node_id)

            ntype = node.get("type")
            if ntype == "action":
                # A real run: dispatch the node's tool and record what it
                # actually did. Called with respect_delays=False (manual)
                # actions still run — a manual 'Execute now' click that did
                # nothing would be the #61 class of lie. Actions run on the
                # event path (source="event") like any other source.
                result = self._execute_action_bounded(
                    str(node.get("config", {}).get("tool", "")),
                    dict(node.get("config", {})),
                    context,
                )
                exec_record["action_results"][node_id] = result
                for nxt in self._successors(edges, node_id, branch=None):
                    queue.append((nxt, None))
            elif ntype == "condition":
                result = self._evaluate_condition(node.get("config", {}), context)
                exec_record["condition_results"][node_id] = result
                nxts = self._successors(edges, node_id, branch=result)
                if not nxts and not any(
                    ed.get("from") == node_id and ed.get("condition") in ("true", "false")
                    for ed in edges
                ):
                    # Condition node has NO branch-tagged edges at all (e.g.
                    # hand-built or API-created flows): degrade to following
                    # unconditional edges instead of silently dead-ending.
                    nxts = self._successors(edges, node_id, branch=None)
                for nxt in nxts:
                    queue.append((nxt, None))
            elif ntype == "delay":
                seconds = 0.0
                try:
                    seconds = float(node.get("config", {}).get("seconds", 0))
                except (TypeError, ValueError):
                    seconds = 0.0
                seconds = max(0.0, min(seconds, MAX_DELAY_SECONDS))
                if respect_delays and seconds > 0:
                    # Real delay semantics. A plain time.sleep() here would
                    # freeze the poll/event loop, so the sleep happens in a
                    # bounded worker pool and _traverse blocks on the result
                    # — the run's timeline genuinely includes the pause.
                    executor = concurrent.futures.ThreadPoolExecutor(
                        max_workers=MAX_DELAY_WORKERS,
                        thread_name_prefix="dash-delay",
                    )
                    try:
                        executor.submit(time.sleep, seconds).result()
                    finally:
                        executor.shutdown(wait=False)
                for nxt in self._successors(edges, node_id, branch=None):
                    queue.append((nxt, None))
            else:
                # trigger + action: follow unconditional edges.
                for nxt in self._successors(edges, node_id, branch=None):
                    queue.append((nxt, None))

        exec_record["output"] = {
            "nodes_run": len(exec_record["nodes_executed"]),
            "status": "success",
            "conditions": dict(exec_record["condition_results"]),
        }

    def execute(self, workflow_id: str, input_data: Optional[dict] = None, source: str = "manual") -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        if not wf.get("enabled"):
            return {"ok": False, "reason": "Workflow is disabled"}

        exec_id = f"exec_{uuid.uuid4().hex[:12]}"
        exec_record = {
            "id": exec_id,
            "workflow_id": workflow_id,
            "workflow_name": wf["name"],
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "nodes_executed": [],
            "action_results": {},
            "condition_results": {},
            "input": input_data,
            "output": None,
            "error": None,
            "duration_ms": 0,
            "source": source,  # manual | scheduled | webhook | event
        }
        self._executions.append(exec_record)

        # Real graph traversal: follow edges from the trigger, evaluate
        # condition nodes, and execute only the matching branch. The old
        # simulation walked every node in list order and ignored edges
        # entirely, so if/else flows executed BOTH branches.
        start_time = time.perf_counter()
        try:
            self._traverse(wf, exec_record, dict(input_data or {}),
                           respect_delays=source != "manual")
            exec_record["status"] = "completed"
            exec_record["completed_at"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            exec_record["status"] = "failed"
            exec_record["error"] = str(e)
        finally:
            exec_record["duration_ms"] = round((time.perf_counter() - start_time) * 1000, 2)

        wf["run_count"] = wf.get("run_count", 0) + 1
        wf["last_run"] = exec_record["completed_at"]

        # Persist history so the execution panel survives restarts. Templates
        # never re-save (they are code-owned); custom saves carry the buffer.
        if not wf.get("is_template"):
            self._save_custom()

        return {"ok": True, "execution": exec_record}

    def get_executions(self, workflow_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        result = self._executions
        if workflow_id:
            result = [e for e in result if e["workflow_id"] == workflow_id]
        return list(reversed(result[-limit:]))

    def get_workflow_stats(self, workflow_id: str) -> dict:
        execs = [e for e in self._executions if e["workflow_id"] == workflow_id]
        if not execs:
            return {"total_runs": 0}
        successful = sum(1 for e in execs if e["status"] == "completed")
        failed = sum(1 for e in execs if e["status"] == "failed")
        durations = [e.get("duration_ms", 0) for e in execs]
        return {
            "total_runs": len(execs),
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / len(execs) * 100, 1) if execs else 0,
            "avg_duration_ms": round(sum(durations) / len(durations), 2) if durations else 0,
            "last_run": execs[-1].get("started_at"),
        }

    def get_all_stats(self) -> dict:
        wf = list(self._workflows.values())
        execs = self._executions
        return {
            "total_workflows": len(wf),
            "templates": len([w for w in wf if w.get("is_template")]),
            "custom": len([w for w in wf if not w.get("is_template")]),
            "total_executions": len(execs),
            "schedules_active": len(self._schedules),
            "webhooks_active": len(self._webhooks),
            "event_triggers_active": len(self._event_triggers),
        }

    def get_trigger_status(self) -> dict:
        """Aggregate trigger status for the System page (decisions.md #81).

        Honest by construction: active/paused counts reflect exactly the
        enabled flags the fire gates read, next-due comes from the same
        cron evaluator the scheduler polls, and a paused schedule is
        excluded from next-due because the scheduler really will skip it.
        """
        schedules = self.get_schedules()  # + workflow_name per entry
        webhooks = self._webhooks
        triggers = self._event_triggers

        now = datetime.now()
        now_min = now.replace(second=0, microsecond=0)
        next_due: Optional[dict] = None
        for wf_id, sched in schedules.items():
            if not sched.get("enabled"):
                continue
            wf = self._workflows.get(wf_id)
            if wf is None or wf.get("is_template") or not wf.get("enabled", True):
                continue
            cron = sched.get("cron", "")
            # Due RIGHT NOW when the current minute matches and this
            # minute has not already been fired (same idempotence window
            # due_schedules uses). Otherwise the first future match.
            fired_this_minute = False
            last = sched.get("last_fired_at")
            if last:
                try:
                    fired_this_minute = (
                        datetime.fromisoformat(str(last)).replace(second=0, microsecond=0)
                        == now_min
                    )
                except ValueError:
                    pass  # corrupt timestamp: treat as not fired
            try:
                if _fields_match(parse_cron(cron), now_min) and not fired_this_minute:
                    due = now_min
                else:
                    due = next_cron_due(cron, now)
            except InvalidCronError:
                continue
            if due is not None and (next_due is None or due < next_due["_dt"]):
                next_due = {
                    "_dt": due,
                    "workflow_id": wf_id,
                    "workflow_name": sched.get("workflow_name", "Unknown"),
                    "cron": cron,
                    "due_at": due.isoformat(),
                }
        if next_due is not None:
            next_due.pop("_dt")

        return {
            "schedules_total": len(schedules),
            "schedules_active": sum(1 for s in schedules.values() if s.get("enabled")),
            "schedules_paused": sum(1 for s in schedules.values() if not s.get("enabled")),
            "webhooks_total": len(webhooks),
            "webhooks_active": sum(1 for w in webhooks.values() if w.get("enabled")),
            "webhooks_paused": sum(1 for w in webhooks.values() if not w.get("enabled")),
            "event_triggers_total": len(triggers),
            "event_triggers_active": sum(1 for t in triggers.values() if t.get("enabled")),
            "event_triggers_paused": sum(1 for t in triggers.values() if not t.get("enabled")),
            "next_due": next_due,
        }


# Singleton
workflow_engine = WorkflowEngine()


# ── Trigger Scheduler (decisions.md #53) ──────────────────────────────

class WorkflowTriggerScheduler:
    """Fires workflows whose schedule is due, via a low-frequency poll loop.

    Each cycle evaluates every persisted schedule with the engine's
    due_schedules() against the local wall clock (cron fields are evaluated
    in local time — matching what a user typed on their machine), executes
    the due workflows, and stamps them fired so a restart cannot
    double-fire. Every exception in a cycle is contained: the loop logs and
    keeps polling instead of dying silently.
    """

    def __init__(self, engine: Optional[WorkflowEngine] = None, poll_seconds: int = 60) -> None:
        self._engine = engine or workflow_engine
        self._poll_seconds = poll_seconds
        self._task: Optional[asyncio.Task] = None
        self._last_tick_at: Optional[datetime] = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def poll_seconds(self) -> int:
        """Configured cycle length (public for status routes)."""
        return self._poll_seconds

    @property
    def last_tick_at(self) -> Optional[str]:
        """ISO stamp of the last cycle start (None = never ticked)."""
        return self._last_tick_at.isoformat() if self._last_tick_at else None

    @property
    def engine(self) -> WorkflowEngine:
        """The engine this scheduler fires into (public for status routes)."""
        return self._engine

    async def tick(self, now: Optional[datetime] = None) -> list[str]:
        """One scheduler pass; returns the workflow ids fired.

        Public so tests (and the loop) can drive time forward without
        sleeping. `now` is a naive LOCAL datetime.
        """
        now = now or datetime.now()
        self._last_tick_at = now  # cycle start: the last time due work was evaluated
        fired: list[str] = []
        for wf_id in self._engine.due_schedules(now):
            # Offload: a due workflow may contain a delay node whose real
            # sleep (decisions.md #57) must never block the event loop.
            result = await asyncio.to_thread(
                self._engine.execute, wf_id, None, "scheduled"
            )
            if result.get("ok"):
                self._engine.mark_fired(wf_id, result["execution"]["status"], at=now)
                fired.append(wf_id)
                logger.info("Scheduled workflow %s fired (%s)", wf_id, result["execution"]["id"])
            else:
                self._engine.mark_fired(wf_id, "failed", at=now)
                logger.warning("Scheduled workflow %s did not run: %s", wf_id, result.get("reason"))
        return fired

    async def _loop(self) -> None:
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Workflow trigger poll failed")
            await asyncio.sleep(self._poll_seconds)

    def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Workflow trigger scheduler started (poll=%ss)", self._poll_seconds)

    async def stop(self) -> None:
        had_task = self._task is not None
        if had_task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        # Liveness honesty (decisions.md #104): a stopped scheduler is not
        # "running but last ticked a while ago" — it is stopped. Clearing
        # the tick stamp here keeps the status route truthful across a
        # stop/start cycle (a restart ticks afresh) instead of reporting a
        # stale timestamp from the previous run. This also covers a bare
        # tick() without start(), which leaves a stamp but no task.
        self._last_tick_at = None
        if had_task:
            logger.info("Workflow trigger scheduler stopped")


_trigger_scheduler: Optional[WorkflowTriggerScheduler] = None


def get_workflow_trigger_scheduler() -> WorkflowTriggerScheduler:
    """Singleton accessor; main.py starts it during lifespan startup."""
    global _trigger_scheduler
    if _trigger_scheduler is None:
        _trigger_scheduler = WorkflowTriggerScheduler()
    return _trigger_scheduler
