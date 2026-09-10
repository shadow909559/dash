"""Collaboration: multi-user, shared workspaces, roles, comments, mentions.

Workspaces, memberships, comments, and the activity feed persist to the
shared local SQLite store and survive backend restarts.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from dash_backend.services.local_store import LocalStore, new_id

logger = logging.getLogger(__name__)

ROLES = ["admin", "editor", "viewer"]


class WorkspaceService:
    """Shared workspaces and role-based access (persisted)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._workspaces: list[dict] = self._store.list_docs("workspaces")
        self._members: dict[str, list[dict]] = {}
        for row in self._store.query("SELECT workspace_id, user_id, data FROM workspace_members ORDER BY rowid"):
            self._members.setdefault(row["workspace_id"], []).append(json.loads(row["data"]))

    def _persist_members(self, ws_id: str) -> None:
        self._store.execute("DELETE FROM workspace_members WHERE workspace_id = ?", (ws_id,))
        for m in self._members.get(ws_id, []):
            self._store.execute(
                "INSERT INTO workspace_members (workspace_id, user_id, data) VALUES (?, ?, ?)",
                (ws_id, m["user_id"], json.dumps(m)),
            )

    def create(self, name: str, owner_id: str, description: str = "") -> dict:
        ws = {"id": new_id("ws"), "name": name, "description": description,
              "owner": owner_id, "created_at": datetime.now(timezone.utc).isoformat()}
        self._workspaces.append(ws)
        self._members[ws["id"]] = [{"user_id": owner_id, "role": "admin", "joined_at": ws["created_at"]}]
        self._store.put_doc("workspaces", ws["id"], ws, seq=self._store.next_seq("workspaces"))
        self._persist_members(ws["id"])
        return {"ok": True, "workspace": ws}

    def list_all(self) -> list[dict]:
        return self._workspaces

    def get(self, ws_id: str) -> Optional[dict]:
        return next((w for w in self._workspaces if w["id"] == ws_id), None)

    def delete(self, ws_id: str) -> dict:
        self._workspaces = [w for w in self._workspaces if w["id"] != ws_id]
        self._members.pop(ws_id, None)
        self._store.delete_doc("workspaces", ws_id)
        self._store.execute("DELETE FROM workspace_members WHERE workspace_id = ?", (ws_id,))
        return {"ok": True}

    def add_member(self, ws_id: str, user_id: str, role: str = "viewer") -> dict:
        if role not in ROLES:
            return {"ok": False, "reason": f"Invalid role. Use: {ROLES}"}
        members = self._members.get(ws_id, [])
        if any(m["user_id"] == user_id for m in members):
            return {"ok": False, "reason": "Already a member"}
        members.append({"user_id": user_id, "role": role, "joined_at": datetime.now(timezone.utc).isoformat()})
        self._members[ws_id] = members
        self._persist_members(ws_id)
        return {"ok": True}

    def remove_member(self, ws_id: str, user_id: str) -> dict:
        self._members[ws_id] = [m for m in self._members.get(ws_id, []) if m["user_id"] != user_id]
        self._persist_members(ws_id)
        return {"ok": True}

    def update_role(self, ws_id: str, user_id: str, new_role: str) -> dict:
        if new_role not in ROLES:
            return {"ok": False, "reason": f"Invalid role. Use: {ROLES}"}
        for m in self._members.get(ws_id, []):
            if m["user_id"] == user_id:
                m["role"] = new_role
                self._persist_members(ws_id)
                return {"ok": True}
        return {"ok": False, "reason": "Member not found"}

    def get_members(self, ws_id: str) -> list[dict]:
        return self._members.get(ws_id, [])

    def check_permission(self, ws_id: str, user_id: str, required_role: str) -> bool:
        role_hierarchy = {"admin": 3, "editor": 2, "viewer": 1}
        for m in self._members.get(ws_id, []):
            if m["user_id"] == user_id:
                return role_hierarchy.get(m["role"], 0) >= role_hierarchy.get(required_role, 0)
        return False


class CommentService:
    """Comments on memories, goals, code, and any entity (persisted)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._comments: list[dict] = self._store.list_docs("comments")

    def add(self, entity_type: str, entity_id: str, author_id: str, content: str) -> dict:
        comment = {"id": new_id("cmt"), "entity_type": entity_type, "entity_id": entity_id,
                   "author_id": author_id, "content": content, "created_at": datetime.now(timezone.utc).isoformat(),
                   "edited": False, "mentions": self._extract_mentions(content)}
        self._comments.append(comment)
        self._store.put_doc("comments", comment["id"], comment, seq=self._store.next_seq("comments"))
        return {"ok": True, "comment": comment}

    def get_for_entity(self, entity_type: str, entity_id: str) -> list[dict]:
        return [c for c in self._comments if c["entity_type"] == entity_type and c["entity_id"] == entity_id]

    def edit(self, comment_id: str, new_content: str) -> dict:
        for c in self._comments:
            if c["id"] == comment_id:
                c["content"] = new_content
                c["edited"] = True
                c["edited_at"] = datetime.now(timezone.utc).isoformat()
                self._store.put_doc("comments", c["id"], c)
                return {"ok": True, "comment": c}
        return {"ok": False, "reason": "Comment not found"}

    def delete(self, comment_id: str) -> dict:
        self._comments = [c for c in self._comments if c["id"] != comment_id]
        self._store.delete_doc("comments", comment_id)
        return {"ok": True}

    def get_mentions_for_user(self, user_id: str) -> list[dict]:
        return [c for c in self._comments if f"@{user_id}" in c.get("content", "")]

    @staticmethod
    def _extract_mentions(text: str) -> list[str]:
        import re
        return re.findall(r'@(\w+)', text)


class ActivityFeedService:
    """Collaborative activity feed across workspaces (persisted)."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        rows = self._store.query("SELECT data FROM activity_events ORDER BY id ASC")
        self._events: list[dict] = [json.loads(r["data"]) for r in rows]

    def record(self, user_id: str, action: str, entity_type: str = "", entity_id: str = "",
               details: str = "", workspace_id: str = "") -> dict:
        event = {"id": new_id("evt"), "user_id": user_id, "action": action,
                 "entity_type": entity_type, "entity_id": entity_id, "details": details,
                 "workspace_id": workspace_id, "timestamp": datetime.now(timezone.utc).isoformat()}
        self._events.append(event)
        if len(self._events) > 5000:
            self._events = self._events[-2500:]
            self._store.execute("DELETE FROM activity_events")
            for e in self._events:
                self._store.execute(
                    "INSERT INTO activity_events (workspace_id, user_id, data) VALUES (?, ?, ?)",
                    (e.get("workspace_id", ""), e.get("user_id", ""), json.dumps(e)),
                )
            return {"ok": True, "event": event}
        self._store.execute("INSERT INTO activity_events (workspace_id, user_id, data) VALUES (?, ?, ?)",
                            (workspace_id, user_id, json.dumps(event)))
        return {"ok": True, "event": event}

    def get_feed(self, workspace_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        result = self._events
        if workspace_id:
            result = [e for e in result if e.get("workspace_id") == workspace_id]
        return list(reversed(result[-limit:]))

    def get_user_activity(self, user_id: str, limit: int = 50) -> list[dict]:
        return list(reversed([e for e in self._events if e.get("user_id") == user_id][-limit:]))


workspace_service = WorkspaceService()
comment_service = CommentService()
activity_feed = ActivityFeedService()
