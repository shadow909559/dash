"""Email, calendar, and contact management integration.

All state persists to the shared local SQLite store (local_store.py) so
accounts, mail, events, reminders, contacts, and rules survive backend
restarts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from dash_backend.services.local_store import LocalStore, new_id

logger = logging.getLogger(__name__)


class EmailService:
    """Email read/send/search integration (persisted)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._accounts: list[dict] = self._store.list_docs("email_accounts")
        self._inbox: list[dict] = self._store.list_docs("emails", newest_first=True)
        self._sent: list[dict] = []
        self._rules: list[dict] = self._store.list_docs("email_rules")

    def add_account(self, email: str, provider: str = "imap", display_name: str = "") -> dict:
        account = {
            "id": new_id("acct"),
            "email": email,
            "provider": provider,
            "display_name": display_name or email.split("@")[0],
            "connected_at": datetime.now(timezone.utc).isoformat(),
            "status": "connected",
        }
        self._accounts.append(account)
        self._store.put_doc("email_accounts", account["id"], account, seq=self._store.next_seq("email_accounts"))
        return {"ok": True, "account": account}

    def list_accounts(self) -> list[dict]:
        return self._accounts

    def receive_email(self, from_addr: str, subject: str, body: str,
                      importance: float = 0.5, labels: list[str] | None = None) -> dict:
        email = {
            "id": new_id("email"),
            "from": from_addr,
            "subject": subject,
            "body": body,
            "importance": importance,
            "labels": labels or [],
            "read": False,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        self._inbox.append(email)
        self._store.put_doc("emails", email["id"], email, seq=self._store.next_seq("emails"))
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
                self._store.put_doc("emails", e["id"], e)
                return {"ok": True}
        return {"ok": False, "reason": "Email not found"}

    def add_rule(self, name: str, condition: dict, action: str, action_config: dict) -> dict:
        rule = {
            "id": new_id("rule"),
            "name": name,
            "condition": condition,
            "action": action,
            "action_config": action_config,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._rules.append(rule)
        self._store.put_doc("email_rules", rule["id"], rule, seq=self._store.next_seq("email_rules"))
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
    """Calendar sync, event management, scheduling (persisted)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._calendars: list[dict] = self._store.list_docs("calendars")
        self._events: list[dict] = self._store.list_docs("calendar_events")
        self._reminders: list[dict] = self._store.list_docs("calendar_reminders")

    def add_calendar(self, name: str, provider: str = "local", color: str = "#22c55e") -> dict:
        cal = {
            "id": new_id("cal"),
            "name": name,
            "provider": provider,
            "color": color,
            "event_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._calendars.append(cal)
        self._store.put_doc("calendars", cal["id"], cal, seq=self._store.next_seq("calendars"))
        return {"ok": True, "calendar": cal}

    def list_calendars(self) -> list[dict]:
        return self._calendars

    def create_event(self, title: str, start: str, end: str, calendar_id: str = "0",
                     description: str = "", location: str = "", recurrence: str = "",
                     attendees: list[str] | None = None) -> dict:
        event = {
            "id": new_id("evt"),
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
        self._store.put_doc("calendar_events", event["id"], event, seq=self._store.next_seq("calendar_events"))
        for cal in self._calendars:
            if cal["id"] == calendar_id:
                cal["event_count"] += 1
                self._store.put_doc("calendars", cal["id"], cal)
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
            "id": new_id("rem"),
            "event_id": event_id,
            "minutes_before": minutes_before,
            "fired": False,
        }
        self._reminders.append(reminder)
        for e in self._events:
            if e["id"] == event_id:
                e["reminders"].append(reminder["id"])
                self._store.put_doc("calendar_events", e["id"], e)
        self._store.put_doc("calendar_reminders", reminder["id"], reminder, seq=self._store.next_seq("calendar_reminders"))
        return {"ok": True, "reminder": reminder}

    def update_event(self, event_id: str, **kwargs) -> dict:
        for e in self._events:
            if e["id"] == event_id:
                for k, v in kwargs.items():
                    if k in ("title", "start", "end", "description", "location", "status"):
                        e[k] = v
                self._store.put_doc("calendar_events", e["id"], e)
                return {"ok": True, "event": e}
        return {"ok": False, "reason": "Event not found"}

    def delete_event(self, event_id: str) -> dict:
        before = len(self._events)
        self._events = [e for e in self._events if e["id"] != event_id]
        self._store.delete_doc("calendar_events", event_id)
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
    """Contact management (persisted)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._contacts: list[dict] = self._store.list_docs("contacts")
        self._groups: list[dict] = self._store.list_docs("contact_groups")

    def add_contact(self, name: str, email: str = "", phone: str = "",
                    company: str = "", notes: str = "", tags: list[str] | None = None) -> dict:
        contact = {
            "id": new_id("contact"),
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
        self._store.put_doc("contacts", contact["id"], contact, seq=self._store.next_seq("contacts"))
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
                self._store.put_doc("contacts", c["id"], c)
                return {"ok": True, "contact": c}
        return {"ok": False, "reason": "Contact not found"}

    def delete_contact(self, contact_id: str) -> dict:
        self._contacts = [c for c in self._contacts if c["id"] != contact_id]
        self._store.delete_doc("contacts", contact_id)
        return {"ok": True}

    def record_interaction(self, contact_id: str, interaction_type: str = "message") -> dict:
        for c in self._contacts:
            if c["id"] == contact_id:
                c["interaction_count"] += 1
                c["last_interaction"] = datetime.now(timezone.utc).isoformat()
                self._store.put_doc("contacts", c["id"], c)
                return {"ok": True}
        return {"ok": False, "reason": "Contact not found"}

    def add_group(self, name: str, description: str = "") -> dict:
        group = {"id": new_id("group"), "name": name, "description": description, "members": []}
        self._groups.append(group)
        self._store.put_doc("contact_groups", group["id"], group, seq=self._store.next_seq("contact_groups"))
        return {"ok": True, "group": group}

    def add_to_group(self, group_id: str, contact_id: str) -> dict:
        for g in self._groups:
            if g["id"] == group_id:
                if contact_id not in g["members"]:
                    g["members"].append(contact_id)
                    self._store.put_doc("contact_groups", g["id"], g)
                return {"ok": True}
        return {"ok": False, "reason": "Group not found"}

    def get_stats(self) -> dict:
        companies = set(c.get("company", "") for c in self._contacts if c.get("company"))
        return {"total_contacts": len(self._contacts), "groups": len(self._groups), "unique_companies": len(companies)}


email_service = EmailService()
calendar_service = CalendarService()
contact_service = ContactService()
