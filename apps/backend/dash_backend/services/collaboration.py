"""Collaboration: multi-user, shared workspaces, roles, comments, mentions."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

ROLES = ["admin", "editor", "viewer"]


class WorkspaceService:
    """Shared workspaces and role-based access."""

    def __init__(self) -> None:
        self._workspaces: list[dict] = []
        self._members: dict[str, list[dict]] = {}

    def create(self, name: str, owner_id: str, description: str = "") -> dict:
        ws = {"id": f"ws_{len(self._workspaces)}", "name": name, "description": description,
              "owner": owner_id, "created_at": datetime.now(timezone.utc).isoformat()}
        self._workspaces.append(ws)
        self._members[ws["id"]] = [{"user_id": owner_id, "role": "admin", "joined_at": ws["created_at"]}]
        return {"ok": True, "workspace": ws}

    def list_all(self) -> list[dict]:
        return self._workspaces

    def get(self, ws_id: str) -> Optional[dict]:
        return next((w for w in self._workspaces if w["id"] == ws_id), None)

    def delete(self, ws_id: str) -> dict:
        self._workspaces = [w for w in self._workspaces if w["id"] != ws_id]
        self._members.pop(ws_id, None)
        return {"ok": True}

    def add_member(self, ws_id: str, user_id: str, role: str = "viewer") -> dict:
        if role not in ROLES:
            return {"ok": False, "reason": f"Invalid role. Use: {ROLES}"}
        members = self._members.get(ws_id, [])
        if any(m["user_id"] == user_id for m in members):
            return {"ok": False, "reason": "Already a member"}
        members.append({"user_id": user_id, "role": role, "joined_at": datetime.now(timezone.utc).isoformat()})
        self._members[ws_id] = members
        return {"ok": True}

    def remove_member(self, ws_id: str, user_id: str) -> dict:
        self._members[ws_id] = [m for m in self._members.get(ws_id, []) if m["user_id"] != user_id]
        return {"ok": True}

    def update_role(self, ws_id: str, user_id: str, new_role: str) -> dict:
        if new_role not in ROLES:
            return {"ok": False, "reason": f"Invalid role. Use: {ROLES}"}
        for m in self._members.get(ws_id, []):
            if m["user_id"] == user_id:
                m["role"] = new_role
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
    """Comments on memories, goals, code, and any entity."""

    def __init__(self) -> None:
        self._comments: list[dict] = []

    def add(self, entity_type: str, entity_id: str, author_id: str, content: str) -> dict:
        comment = {"id": f"cmt_{len(self._comments)}", "entity_type": entity_type, "entity_id": entity_id,
                   "author_id": author_id, "content": content, "created_at": datetime.now(timezone.utc).isoformat(),
                   "edited": False, "mentions": self._extract_mentions(content)}
        self._comments.append(comment)
        return {"ok": True, "comment": comment}

    def get_for_entity(self, entity_type: str, entity_id: str) -> list[dict]:
        return [c for c in self._comments if c["entity_type"] == entity_type and c["entity_id"] == entity_id]

    def edit(self, comment_id: str, new_content: str) -> dict:
        for c in self._comments:
            if c["id"] == comment_id:
                c["content"] = new_content
                c["edited"] = True
                c["edited_at"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True, "comment": c}
        return {"ok": False, "reason": "Comment not found"}

    def delete(self, comment_id: str) -> dict:
        self._comments = [c for c in self._comments if c["id"] != comment_id]
        return {"ok": True}

    def get_mentions_for_user(self, user_id: str) -> list[dict]:
        return [c for c in self._comments if f"@{user_id}" in c.get("content", "")]

    @staticmethod
    def _extract_mentions(text: str) -> list[str]:
        import re
        return re.findall(r'@(\w+)', text)


class ActivityFeedService:
    """Collaborative activity feed across workspaces."""

    def __init__(self) -> None:
        self._events: list[dict] = []

    def record(self, user_id: str, action: str, entity_type: str = "", entity_id: str = "",
               details: str = "", workspace_id: str = "") -> dict:
        event = {"id": f"evt_{len(self._events)}", "user_id": user_id, "action": action,
                 "entity_type": entity_type, "entity_id": entity_id, "details": details,
                 "workspace_id": workspace_id, "timestamp": datetime.now(timezone.utc).isoformat()}
        self._events.append(event)
        if len(self._events) > 5000:
            self._events = self._events[-2500:]
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
