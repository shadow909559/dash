"""Project management: meeting notes, action items, time tracking, sprints, burndown, gantt, contacts, reminders."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MeetingNotesService:
    """Auto-generate meeting notes from calendar events."""

    def __init__(self) -> None:
        self._notes: list[dict] = []

    def create(self, title: str, attendees: list[str], content: str = "", action_items: list[str] | None = None) -> dict:
        note = {"id": f"note_{len(self._notes)}", "title": title, "attendees": attendees, "content": content, "action_items": action_items or [], "created_at": datetime.now(timezone.utc).isoformat()}
        self._notes.append(note)
        return {"ok": True, "note": note}

    def get_all(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._notes[-limit:]))

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [n for n in self._notes if q in n.get("title", "").lower() or q in n.get("content", "").lower()]

    def update(self, note_id: str, **kwargs) -> dict:
        for n in self._notes:
            if n["id"] == note_id:
                for k, v in kwargs.items():
                    if k in ("title", "content", "action_items", "attendees"):
                        n[k] = v
                return {"ok": True}
        return {"ok": False}

    def delete(self, note_id: str) -> dict:
        self._notes = [n for n in self._notes if n["id"] != note_id]
        return {"ok": True}


class ActionItemService:
    """Track action items extracted from meetings and conversations."""

    def __init__(self) -> None:
        self._items: list[dict] = []

    def create(self, title: str, assignee: str = "", due_date: str = "", source: str = "manual", priority: str = "medium") -> dict:
        item = {"id": f"action_{len(self._items)}", "title": title, "assignee": assignee, "due_date": due_date, "source": source, "priority": priority, "status": "pending", "created_at": datetime.now(timezone.utc).isoformat()}
        self._items.append(item)
        return {"ok": True, "item": item}

    def complete(self, item_id: str) -> dict:
        for i in self._items:
            if i["id"] == item_id:
                i["status"] = "completed"
                i["completed_at"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True}
        return {"ok": False}

    def get_pending(self) -> list[dict]:
        return [i for i in self._items if i["status"] == "pending"]

    def get_all(self, status: Optional[str] = None) -> list[dict]:
        if status:
            return [i for i in self._items if i["status"] == status]
        return list(self._items)

    def get_overdue(self) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        return [i for i in self._items if i["status"] == "pending" and i.get("due_date", "") < now]

    def update(self, item_id: str, **kwargs) -> dict:
        for i in self._items:
            if i["id"] == item_id:
                for k, v in kwargs.items():
                    if k in ("title", "assignee", "due_date", "priority", "status"):
                        i[k] = v
                return {"ok": True}
        return {"ok": False}

    def delete(self, item_id: str) -> dict:
        self._items = [i for i in self._items if i["id"] != item_id]
        return {"ok": True}


class TimeTrackingService:
    """Auto-track time spent on tasks."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._active: Optional[dict] = None

    def start(self, task_name: str, project: str = "") -> dict:
        if self._active:
            self.stop()
        entry = {"id": f"time_{len(self._entries)}", "task": task_name, "project": project, "start": datetime.now(timezone.utc).isoformat(), "end": None, "duration_seconds": 0}
        self._active = entry
        return {"ok": True, "entry": entry}

    def stop(self) -> dict:
        if not self._active:
            return {"ok": False, "reason": "No active timer"}
        self._active["end"] = datetime.now(timezone.utc).isoformat()
        start = datetime.fromisoformat(self._active["start"])
        end = datetime.fromisoformat(self._active["end"])
        self._active["duration_seconds"] = (end - start).total_seconds()
        self._entries.append(self._active)
        result = dict(self._active)
        self._active = None
        return {"ok": True, "entry": result}

    def get_entries(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._entries[-limit:]))

    def get_active(self) -> Optional[dict]:
        return self._active

    def get_summary(self) -> dict:
        total_seconds = sum(e.get("duration_seconds", 0) for e in self._entries)
        by_project: dict[str, float] = {}
        for e in self._entries:
            p = e.get("project", "unknown")
            by_project[p] = by_project.get(p, 0) + e.get("duration_seconds", 0)
        return {"total_hours": round(total_seconds / 3600, 2), "total_entries": len(self._entries), "by_project": {k: round(v / 3600, 2) for k, v in by_project.items()}}


class SprintService:
    """Sprint planning with velocity tracking."""

    def __init__(self) -> None:
        self._sprints: list[dict] = []
        self._tasks: dict[str, list[dict]] = {}

    def create_sprint(self, name: str, start_date: str, end_date: str, goal: str = "") -> dict:
        sprint = {"id": f"sprint_{len(self._sprints)}", "name": name, "start_date": start_date, "end_date": end_date, "goal": goal, "status": "planning", "created_at": datetime.now(timezone.utc).isoformat()}
        self._sprints.append(sprint)
        self._tasks[sprint["id"]] = []
        return {"ok": True, "sprint": sprint}

    def add_task(self, sprint_id: str, title: str, points: int = 1) -> dict:
        task = {"id": f"task_{len(self._tasks.get(sprint_id, []))}", "title": title, "points": points, "status": "todo", "created_at": datetime.now(timezone.utc).isoformat()}
        self._tasks.setdefault(sprint_id, []).append(task)
        return {"ok": True, "task": task}

    def update_task(self, sprint_id: str, task_id: str, status: str) -> dict:
        for t in self._tasks.get(sprint_id, []):
            if t["id"] == task_id:
                t["status"] = status
                if status == "done":
                    t["completed_at"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True}
        return {"ok": False}

    def get_sprints(self) -> list[dict]:
        return list(self._sprints)

    def get_tasks(self, sprint_id: str) -> list[dict]:
        return self._tasks.get(sprint_id, [])

    def get_velocity(self) -> list[dict]:
        result = []
        for s in self._sprints:
            tasks = self._tasks.get(s["id"], [])
            total_points = sum(t.get("points", 0) for t in tasks)
            completed_points = sum(t.get("points", 0) for t in tasks if t.get("status") == "done")
            result.append({"sprint": s["name"], "total_points": total_points, "completed_points": completed_points, "velocity": completed_points})
        return result

    def start_sprint(self, sprint_id: str) -> dict:
        for s in self._sprints:
            if s["id"] == sprint_id:
                s["status"] = "active"
                return {"ok": True}
        return {"ok": False}

    def complete_sprint(self, sprint_id: str) -> dict:
        for s in self._sprints:
            if s["id"] == sprint_id:
                s["status"] = "completed"
                s["completed_at"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True}
        return {"ok": False}


class ReminderService:
    """Smart reminders with context-awareness."""

    def __init__(self) -> None:
        self._reminders: list[dict] = []

    def create(self, title: str, remind_at: str, context: str = "", recurring: str = "") -> dict:
        reminder = {"id": f"rem_{len(self._reminders)}", "title": title, "remind_at": remind_at, "context": context, "recurring": recurring, "fired": False, "created_at": datetime.now(timezone.utc).isoformat()}
        self._reminders.append(reminder)
        return {"ok": True, "reminder": reminder}

    def get_pending(self) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        return [r for r in self._reminders if not r.get("fired") and r.get("remind_at", "") <= now]

    def get_all(self) -> list[dict]:
        return list(self._reminders)

    def fire(self, reminder_id: str) -> dict:
        for r in self._reminders:
            if r["id"] == reminder_id:
                r["fired"] = True
                r["fired_at"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True}
        return {"ok": False}

    def dismiss(self, reminder_id: str) -> dict:
        return self.fire(reminder_id)

    def delete(self, reminder_id: str) -> dict:
        self._reminders = [r for r in self._reminders if r["id"] != reminder_id]
        return {"ok": True}


meeting_notes = MeetingNotesService()
action_items = ActionItemService()
time_tracking = TimeTrackingService()
sprint_service = SprintService()
reminder_service = ReminderService()
