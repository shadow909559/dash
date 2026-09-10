"""Workflow builder: templates, triggers, conditional logic, error handling, execution history."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
from pathlib import Path as _Path


def _state_path() -> _Path:
    """Custom-workflow state file. Override with DASH_WORKFLOW_STATE for tests."""
    override = os.environ.get("DASH_WORKFLOW_STATE")
    if override:
        return _Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(_Path.home() / "AppData" / "Local")
    return _Path(base) / "DASH" / "workflow_state.json"


# ── Workflow Engine ────────────────────────────────────────────────────────

class WorkflowEngine:
    """Core workflow execution engine.

    Custom (user-built) workflows persist to a JSON state file so canvas
    edits survive backend restarts; templates are always re-seeded from
    code and never persisted.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, dict] = {}
        self._executions: list[dict] = []
        self._schedules: dict[str, dict] = {}
        self._webhooks: dict[str, dict] = {}

        # Register templates
        for tmpl in WORKFLOW_TEMPLATES:
            self._workflows[tmpl["id"]] = {
                **tmpl,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_template": True,
                "enabled": True,
            }
        self._load_custom()

    # ── State file I/O (custom workflows only) ─────────────────────

    def _load_custom(self) -> None:
        try:
            path = _state_path()
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
            path = _state_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _json.dumps({"version": 1, "custom_workflows": custom}, indent=2),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("Workflow state save failed", exc_info=True)

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
        self._save_custom()
        return {"ok": True}

    def get(self, workflow_id: str) -> Optional[dict]:
        return self._workflows.get(workflow_id)

    def list_all(self, category: Optional[str] = None) -> list[dict]:
        result = list(self._workflows.values())
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
            nodes=list(wf["nodes"]),
            edges=list(wf["edges"]),
            description=wf.get("description", ""),
            category=wf.get("category", "custom"),
        )

    # ── Triggers ────────────────────────────────────────────────────

    def add_schedule(self, workflow_id: str, cron: str, timezone_: str = "UTC") -> dict:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {"ok": False, "reason": "Workflow not found"}
        self._schedules[workflow_id] = {
            "cron": cron,
            "timezone": timezone_,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        return {"ok": True, "schedule": self._schedules[workflow_id]}

    def remove_schedule(self, workflow_id: str) -> dict:
        self._schedules.pop(workflow_id, None)
        return {"ok": True}

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
        webhook_id = f"wh_{uuid.uuid4().hex[:16]}"
        self._webhooks[workflow_id] = {
            "webhook_id": webhook_id,
            "secret": secret,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trigger_count": 0,
        }
        return {"ok": True, "webhook": self._webhooks[workflow_id]}

    def remove_webhook(self, workflow_id: str) -> dict:
        self._webhooks.pop(workflow_id, None)
        return {"ok": True}

    def get_webhooks(self) -> dict:
        return dict(self._webhooks)

    # ── Execution ───────────────────────────────────────────────────

    def execute(self, workflow_id: str, input_data: Optional[dict] = None) -> dict:
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
            "input": input_data,
            "output": None,
            "error": None,
            "duration_ms": 0,
        }
        self._executions.append(exec_record)

        # Simulate execution (in production, this calls actual tools)
        import time
        start_time = time.perf_counter()
        try:
            for node in wf["nodes"]:
                exec_record["nodes_executed"].append(node["id"])
            exec_record["status"] = "completed"
            exec_record["completed_at"] = datetime.now(timezone.utc).isoformat()
            exec_record["output"] = {"nodes_run": len(wf["nodes"]), "status": "success"}
        except Exception as e:
            exec_record["status"] = "failed"
            exec_record["error"] = str(e)
        finally:
            exec_record["duration_ms"] = round((time.perf_counter() - start_time) * 1000, 2)

        wf["run_count"] = wf.get("run_count", 0) + 1
        wf["last_run"] = exec_record["completed_at"]

        if len(self._executions) > 1000:
            self._executions = self._executions[-500:]

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
        }


# Singleton
workflow_engine = WorkflowEngine()
