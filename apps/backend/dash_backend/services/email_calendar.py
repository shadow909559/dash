"""Email, calendar, and contact management integration."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EmailService:
    """Email read/send/search integration."""

    def __init__(self) -> None:
        self._accounts: list[dict] = []
        self._inbox: list[dict] = []
        self._sent: list[dict] = []
        self._rules: list[dict] = []

    def add_account(self, email: str, provider: str = "imap", display_name: str = "") -> dict:
        account = {
            "id": f"acct_{len(self._accounts)}",
            "email": email,
            "provider": provider,
            "display_name": display_name or email.split("@")[0],
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "status": "connected",
        }
        self._accounts.append(account)
        return {"ok": True, "account": account}

    def list_accounts(self) -> list[dict]:
        return self._accounts

    def receive_email(self, from_addr: str, subject: str, body: str,
                      importance: float = 0.5, labels: list[str] | None = None) -> dict:
        email = {
            "id": f"email_{len(self._inbox)}",
            "from": from_addr,
            "subject": subject,
            "body": body,
            "importance": importance,
            "labels": labels or [],
            "read": False,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        self._inbox.append(email)
        return {"ok": True, "email": email}

    def search(self, query: str, folder: str = "inbox") -> list[dict]:
        source = self._inbox if folder == "inbox" else self._sent
        q = query.lower()
        return [e for e in source if q in e.get("subject", "").lower() or q in e.get("body", "").lower() or q in e.get("from", "").lower()]

    def get_inbox(self, limit: int = 50, unread_only: bool = False) -> list[dict]:
        result = self._inbox
        if unread_only:
            result = [e for e in result if not e.get("read")]
        return list(reversed(result[-limit:]))

    def mark_read(self, email_id: str) -> dict:
        for e in self._inbox:
            if e["id"] == email_id:
                e["read"] = True
                return {"ok": True}
        return {"ok": False, "reason": "Email not found"}

    def add_rule(self, name: str, condition: dict, action: str, action_config: dict) -> dict:
        rule = {
            "id": f"rule_{len(self._rules)}",
            "name": name,
            "condition": condition,
            "action": action,
            "action_config": action_config,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._rules.append(rule)
        return {"ok": True, "rule": rule}

    def get_rules(self) -> list[dict]:
        return self._rules

    def get_stats(self) -> dict:
        return {
            "total_inbox": len(self._inbox),
            "unread": sum(1 for e in self._inbox if not e.get("read")),
            "total_sent": len(self._sent),
            "accounts": len(self._accounts),
            "rules": len(self._rules),
        }


class CalendarService:
    """Calendar sync, event management, scheduling."""

    def __init__(self) -> None:
        self._calendars: list[dict] = []
        self._events: list[dict] = []
        self._reminders: list[dict] = []

    def add_calendar(self, name: str, provider: str = "local", color: str = "#22c55e") -> dict:
        cal = {
            "id": f"cal_{len(self._calendars)}",
            "name": name,
            "provider": provider,
            "color": color,
            "event_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._calendars.append(cal)
        return {"ok": True, "calendar": cal}

    def list_calendars(self) -> list[dict]:
        return self._calendars

    def create_event(self, title: str, start: str, end: str, calendar_id: str = "0",
                     description: str = "", location: str = "", recurrence: str = "",
                     attendees: list[str] | None = None) -> dict:
        event = {
            "id": f"evt_{len(self._events)}",
            "title": title,
            "start": start,
            "end": end,
            "calendar_id": calendar_id,
            "description": description,
            "location": location,
            "recurrence": recurrence,
            "attendees": attendees or [],
            "reminders": [],
            "status": "confirmed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._events.append(event)
        for cal in self._calendars:
            if cal["id"] == calendar_id:
                cal["event_count"] += 1
        return {"ok": True, "event": event}

    def get_events(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[dict]:
        result = self._events
        if start_date:
            result = [e for e in result if e.get("start", "") >= start_date]
        if end_date:
            result = [e for e in result if e.get("end", "") <= end_date]
        return sorted(result, key=lambda x: x.get("start", ""))

    def get_upcoming(self, days: int = 7) -> list[dict]:
        now = datetime.now(timezone.utc)
        cutoff = (now + timedelta(days=days)).isoformat()
        now_str = now.isoformat()
        return [e for e in self._events if now_str <= e.get("start", "") <= cutoff]

    def add_reminder(self, event_id: str, minutes_before: int = 30) -> dict:
        reminder = {
            "id": f"rem_{len(self._reminders)}",
            "event_id": event_id,
            "minutes_before": minutes_before,
            "fired": False,
        }
        self._reminders.append(reminder)
        for e in self._events:
            if e["id"] == event_id:
                e["reminders"].append(reminder["id"])
        return {"ok": True, "reminder": reminder}

    def update_event(self, event_id: str, **kwargs) -> dict:
        for e in self._events:
            if e["id"] == event_id:
                for k, v in kwargs.items():
                    if k in ("title", "start", "end", "description", "location", "status"):
                        e[k] = v
                return {"ok": True, "event": e}
        return {"ok": False, "reason": "Event not found"}

    def delete_event(self, event_id: str) -> dict:
        before = len(self._events)
        self._events = [e for e in self._events if e["id"] != event_id]
        return {"ok": True, "deleted": before - len(self._events)}

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [e for e in self._events if q in e.get("title", "").lower() or q in e.get("description", "").lower()]

    def get_stats(self) -> dict:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        return {
            "total_events": len(self._events),
            "calendars": len(self._calendars),
            "today_events": sum(1 for e in self._events if e.get("start", "").startswith(today)),
            "reminders_pending": sum(1 for r in self._reminders if not r.get("fired")),
        }


class ContactService:
    """Contact management with AI-powered organization."""

    def __init__(self) -> None:
        self._contacts: list[dict] = []
        self._groups: list[dict] = []

    def add_contact(self, name: str, email: str = "", phone: str = "",
                    company: str = "", notes: str = "", tags: list[str] | None = None) -> dict:
        contact = {
            "id": f"contact_{len(self._contacts)}",
            "name": name,
            "email": email,
            "phone": phone,
            "company": company,
            "notes": notes,
            "tags": tags or [],
            "interaction_count": 0,
            "last_interaction": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._contacts.append(contact)
        return {"ok": True, "contact": contact}

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [c for c in self._contacts if q in c.get("name", "").lower() or q in c.get("email", "").lower() or q in c.get("company", "").lower()]

    def get_all(self) -> list[dict]:
        return sorted(self._contacts, key=lambda x: x.get("name", ""))

    def update_contact(self, contact_id: str, **kwargs) -> dict:
        for c in self._contacts:
            if c["id"] == contact_id:
                for k, v in kwargs.items():
                    if k in ("name", "email", "phone", "company", "notes", "tags"):
                        c[k] = v
                return {"ok": True, "contact": c}
        return {"ok": False, "reason": "Contact not found"}

    def delete_contact(self, contact_id: str) -> dict:
        self._contacts = [c for c in self._contacts if c["id"] != contact_id]
        return {"ok": True}

    def record_interaction(self, contact_id: str, interaction_type: str = "message") -> dict:
        for c in self._contacts:
            if c["id"] == contact_id:
                c["interaction_count"] += 1
                c["last_interaction"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True}
        return {"ok": False, "reason": "Contact not found"}

    def add_group(self, name: str, description: str = "") -> dict:
        group = {"id": f"group_{len(self._groups)}", "name": name, "description": description, "members": []}
        self._groups.append(group)
        return {"ok": True, "group": group}

    def add_to_group(self, group_id: str, contact_id: str) -> dict:
        for g in self._groups:
            if g["id"] == group_id:
                if contact_id not in g["members"]:
                    g["members"].append(contact_id)
                return {"ok": True}
        return {"ok": False, "reason": "Group not found"}

    def get_stats(self) -> dict:
        companies = set(c.get("company", "") for c in self._contacts if c.get("company"))
        return {"total_contacts": len(self._contacts), "groups": len(self._groups), "unique_companies": len(companies)}


email_service = EmailService()
calendar_service = CalendarService()
contact_service = ContactService()
