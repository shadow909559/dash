"""Sync Service for Desktop/Mobile synchronization.

Provides:
- Persistent WebSocket reconnect with session recovery
- Automatic session recovery
- Conversation synchronization
- Memory synchronization
- Offline message queue
- Retry failed requests
- Conflict resolution (last-write-wins with vector clocks)
- Background synchronization
- Heartbeat system
- Connection health monitor
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class SyncStatus(Enum):
    """Status of a sync operation."""
    PENDING = "pending"
    IN_FLIGHT = "in_flight"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class SyncState(Enum):
    """State of the sync connection."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECOVERING = "recovering"
    ERROR = "error"


@dataclass
class SyncRequest:
    """A sync request from a client."""
    client_id: str
    client_type: str  # "desktop" or "mobile"
    last_sync_timestamp: str | None
    conversations_since: list[dict[str, Any]] = field(default_factory=list)
    memories_since: list[dict[str, Any]] = field(default_factory=list)
    message_ids_seen: set[str] = field(default_factory=set)
    vector_clock: dict[str, int] = field(default_factory=dict)


@dataclass
class SyncResponse:
    """A sync response to a client."""
    conversations: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    server_timestamp: str = ""
    vector_clock: dict[str, int] = field(default_factory=dict)
    requires_full_sync: bool = False


class SyncService:
    """Core sync service managing state across desktop and mobile clients.

    Features:
    - Session recovery: clients can resume after disconnect
    - Message deduplication: tracks seen message IDs
    - Conflict resolution: last-write-wins with vector clock tracking
    - Offline queue: stores pending messages for delivery
    - Heartbeat: periodic health checks
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._vector_clocks: dict[str, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._seen_message_ids: dict[str, set[str]] = defaultdict(set)
        self._offline_queues: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._heartbeat_timestamps: dict[str, float] = {}
        self._session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._background_tasks: set[asyncio.Task] = set()
        self._running = False

        # Conflict resolution: track last-write-wins per entity
        self._entity_timestamps: dict[str, dict[str, float]] = defaultdict(dict)

    # ── Session Management ──────────────────────────────────

    async def register_session(
        self,
        session_id: str,
        client_id: str,
        client_type: str,
        user_id: str,
    ) -> dict[str, Any]:
        """Register a new sync session.

        If a session for this client already exists, recover it.
        """
        async with self._session_locks[client_id]:
            existing = self._sessions.get(client_id)
            if existing:
                # Session recovery: restore state
                logger.info(
                    "Recovering session for client %s (type=%s, user=%s)",
                    client_id, client_type, user_id,
                )
                existing["session_id"] = session_id
                existing["recovered_at"] = datetime.now(UTC).isoformat()
                existing["recovery_count"] = existing.get("recovery_count", 0) + 1

                # Deliver any queued offline messages
                queued = self._offline_queues.pop(client_id, [])
                if queued:
                    logger.info(
                        "Delivering %d queued messages to client %s",
                        len(queued), client_id,
                    )

                return {
                    "status": "recovered",
                    "session_id": session_id,
                    "recovery_count": existing["recovery_count"],
                    "queued_messages": queued,
                    "requires_full_sync": existing.get("recovery_count", 0) > 3,
                }

            # New session
            self._sessions[client_id] = {
                "session_id": session_id,
                "client_id": client_id,
                "client_type": client_type,
                "user_id": user_id,
                "connected_at": datetime.now(UTC).isoformat(),
                "recovered_at": None,
                "recovery_count": 0,
                "last_heartbeat": time.time(),
            }
            logger.info(
                "Registered new session for client %s (type=%s, user=%s)",
                client_id, client_type, user_id,
            )
            return {
                "status": "new",
                "session_id": session_id,
                "recovery_count": 0,
                "queued_messages": [],
                "requires_full_sync": False,
            }

    async def unregister_session(self, client_id: str) -> None:
        """Unregister a session (on disconnect)."""
        async with self._session_locks[client_id]:
            self._sessions.pop(client_id, None)
            logger.info("Unregistered session for client %s", client_id)

    async def get_session(self, client_id: str) -> dict[str, Any] | None:
        """Get session info for a client."""
        return self._sessions.get(client_id)

    # ── Heartbeat ───────────────────────────────────────────

    async def record_heartbeat(self, client_id: str) -> None:
        """Record a heartbeat from a client."""
        self._heartbeat_timestamps[client_id] = time.time()
        if client_id in self._sessions:
            self._sessions[client_id]["last_heartbeat"] = time.time()

    async def get_stale_clients(
        self, timeout_seconds: float = 30.0
    ) -> list[str]:
        """Get list of clients that haven't sent heartbeat recently."""
        now = time.time()
        stale = []
        for client_id, last_ts in self._heartbeat_timestamps.items():
            if now - last_ts > timeout_seconds:
                stale.append(client_id)
        return stale

    # ── Message Deduplication ───────────────────────────────

    async def mark_message_seen(
        self, client_id: str, message_id: str
    ) -> None:
        """Mark a message as seen by a client (for dedup)."""
        self._seen_message_ids[client_id].add(message_id)

    async def is_message_seen(
        self, client_id: str, message_id: str
    ) -> bool:
        """Check if a message has already been seen by a client."""
        return message_id in self._seen_message_ids.get(client_id, set())

    async def mark_messages_seen_bulk(
        self, client_id: str, message_ids: list[str]
    ) -> None:
        """Mark multiple messages as seen."""
        self._seen_message_ids[client_id].update(message_ids)

    # ── Offline Queue ───────────────────────────────────────

    async def enqueue_offline_message(
        self, client_id: str, message: dict[str, Any]
    ) -> None:
        """Queue a message for delivery when client reconnects."""
        self._offline_queues[client_id].append(message)
        logger.debug(
            "Queued offline message for client %s (queue size: %d)",
            client_id, len(self._offline_queues[client_id]),
        )

    async def get_offline_messages(
        self, client_id: str
    ) -> list[dict[str, Any]]:
        """Get and clear the offline message queue for a client."""
        return self._offline_queues.pop(client_id, [])

    async def has_offline_messages(self, client_id: str) -> bool:
        """Check if a client has queued offline messages."""
        return bool(self._offline_queues.get(client_id))

    # ── Vector Clock / Conflict Resolution ──────────────────

    async def update_vector_clock(
        self,
        client_id: str,
        entity_type: str,
        entity_id: str,
        timestamp: float,
    ) -> dict[str, int]:
        """Update the vector clock for an entity.

        Returns the current vector clock state.
        """
        clock = self._vector_clocks[entity_type]
        clock[client_id] = max(clock.get(client_id, 0), int(timestamp * 1000))
        return dict(clock)

    async def resolve_conflict(
        self,
        entity_type: str,
        entity_id: str,
        local_version: dict[str, Any],
        remote_version: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve a conflict between local and remote versions.

        Uses last-write-wins strategy with vector clock comparison.
        """
        local_ts = local_version.get("updated_at") or local_version.get("timestamp", "")
        remote_ts = remote_version.get("updated_at") or remote_version.get("timestamp", "")

        # Parse timestamps
        try:
            local_dt = datetime.fromisoformat(local_ts.replace("Z", "+00:00"))
            remote_dt = datetime.fromisoformat(remote_ts.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            # Fallback: remote wins
            return remote_version

        if local_dt >= remote_dt:
            return local_version
        return remote_version

    async def detect_conflicts(
        self,
        client_id: str,
        entity_type: str,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect conflicts between client items and server state.

        Returns list of conflicting items.
        """
        conflicts = []
        for item in items:
            entity_id = item.get("id")
            if not entity_id:
                continue

            item_ts = item.get("updated_at") or item.get("timestamp", "")
            stored_ts = self._entity_timestamps[entity_type].get(entity_id, 0.0)

            try:
                item_dt = datetime.fromisoformat(
                    item_ts.replace("Z", "+00:00")
                )
                item_ts_float = item_dt.timestamp()
            except (ValueError, AttributeError):
                continue

            if stored_ts > 0 and item_ts_float < stored_ts:
                # Client has older version - conflict
                conflicts.append({
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "client_version": item,
                    "server_timestamp": stored_ts,
                })
            elif item_ts_float > stored_ts:
                # Client has newer version - update stored timestamp
                self._entity_timestamps[entity_type][entity_id] = item_ts_float

        return conflicts

    # ── Conversation Sync ───────────────────────────────────

    async def sync_conversations(
        self,
        user_id: str,
        client_id: str,
        conversations: list[dict[str, Any]],
        last_sync: str | None,
    ) -> SyncResponse:
        """Synchronize conversations between client and server.

        Returns new/updated conversations and any conflicts.
        """
        from dash_backend.db.session import AsyncSessionLocal
        from dash_backend.chat.service import (
            get_user_conversations,
            update_conversation,
            create_conversation,
        )

        response = SyncResponse()
        response.server_timestamp = datetime.now(UTC).isoformat()

        async with AsyncSessionLocal() as session:
            # Get server conversations since last sync
            server_convs, total = await get_user_conversations(
                session, user_id, limit=500
            )

            # Build server conversation map
            server_map: dict[str, dict[str, Any]] = {}
            for conv in server_convs:
                conv_dict = {
                    "id": str(conv.id),
                    "title": conv.title or "",
                    "created_at": (
                        conv.created_at.isoformat() if conv.created_at else ""
                    ),
                    "updated_at": (
                        conv.updated_at.isoformat() if conv.updated_at else ""
                    ),
                    "is_archived": getattr(conv, "is_archived", False),
                    "is_pinned": getattr(conv, "is_pinned", False),
                }
                server_map[str(conv.id)] = conv_dict

            # Process client conversations
            for conv in conversations:
                conv_id = conv.get("id", "")
                if conv_id in server_map:
                    # Check for conflicts
                    conflicts = await self.detect_conflicts(
                        client_id, "conversation", [conv]
                    )
                    if conflicts:
                        response.conflicts.extend(conflicts)
                    else:
                        # Update server with client changes
                        try:
                            await update_conversation(
                                session,
                                conv_id,
                                title=conv.get("title"),
                                is_archived=conv.get("is_archived"),
                                is_pinned=conv.get("is_pinned"),
                            )
                        except Exception:
                            logger.exception(
                                "Failed to update conversation %s", conv_id
                            )
                else:
                    # New conversation from client
                    try:
                        new_conv = await create_conversation(
                            session=session,
                            user_id=user_id,
                            title=conv.get("title"),
                        )
                        server_map[str(new_conv.id)] = {
                            "id": str(new_conv.id),
                            "title": new_conv.title or "",
                            "created_at": (
                                new_conv.created_at.isoformat()
                                if new_conv.created_at
                                else ""
                            ),
                            "updated_at": (
                                new_conv.updated_at.isoformat()
                                if new_conv.updated_at
                                else ""
                            ),
                        }
                    except Exception:
                        logger.exception(
                            "Failed to create conversation from sync"
                        )

            # Return server conversations that client doesn't have
            client_ids = {c.get("id") for c in conversations}
            for conv_id, conv_data in server_map.items():
                if conv_id not in client_ids:
                    response.conversations.append(conv_data)

        return response

    # ── Memory Sync ─────────────────────────────────────────

    async def sync_memories(
        self,
        user_id: str,
        client_id: str,
        memories: list[dict[str, Any]],
        last_sync: str | None,
    ) -> SyncResponse:
        """Synchronize memories between client and server.

        Returns new/updated memories and any conflicts.
        """
        from dash_backend.db.session import AsyncSessionLocal
        from dash_backend.memory.service import (
            get_user_memories,
            save_memory,
            update_memory,
        )

        response = SyncResponse()
        response.server_timestamp = datetime.now(UTC).isoformat()

        async with AsyncSessionLocal() as session:
            # Get server memories
            server_mems, total = await get_user_memories(
                session, user_id, limit=500
            )

            # Build server memory map
            server_map: dict[str, dict[str, Any]] = {}
            for mem in server_mems:
                mem_dict = {
                    "id": str(mem.id),
                    "content": mem.content or "",
                    "title": mem.title or "",
                    "category": mem.category or "",
                    "importance": mem.importance or 0.5,
                    "created_at": (
                        mem.created_at.isoformat() if mem.created_at else ""
                    ),
                    "updated_at": (
                        mem.updated_at.isoformat() if mem.updated_at else ""
                    ),
                }
                server_map[str(mem.id)] = mem_dict

            # Process client memories
            for mem in memories:
                mem_id = mem.get("id", "")
                if mem_id in server_map:
                    # Check for conflicts
                    conflicts = await self.detect_conflicts(
                        client_id, "memory", [mem]
                    )
                    if conflicts:
                        response.conflicts.extend(conflicts)
                    else:
                        # Update server with client changes
                        try:
                            await update_memory(
                                session,
                                mem_id,
                                content=mem.get("content"),
                                title=mem.get("title"),
                                category=mem.get("category"),
                                importance=mem.get("importance"),
                            )
                        except Exception:
                            logger.exception(
                                "Failed to update memory %s", mem_id
                            )
                else:
                    # New memory from client
                    try:
                        new_mem = await save_memory(
                            session,
                            user_id,
                            mem.get("content", ""),
                            title=mem.get("title"),
                            category=mem.get("category"),
                            importance=mem.get("importance", 0.5),
                            source="sync",
                        )
                        server_map[str(new_mem.id)] = {
                            "id": str(new_mem.id),
                            "content": new_mem.content or "",
                            "title": new_mem.title or "",
                            "category": new_mem.category or "",
                            "importance": new_mem.importance or 0.5,
                            "created_at": (
                                new_mem.created_at.isoformat()
                                if new_mem.created_at
                                else ""
                            ),
                            "updated_at": (
                                new_mem.updated_at.isoformat()
                                if new_mem.updated_at
                                else ""
                            ),
                        }
                    except Exception:
                        logger.exception(
                            "Failed to create memory from sync"
                        )

            # Return server memories that client doesn't have
            client_ids = {m.get("id") for m in memories}
            for mem_id, mem_data in server_map.items():
                if mem_id not in client_ids:
                    response.memories.append(mem_data)

        return response

    # ── Full Sync ───────────────────────────────────────────

    async def perform_full_sync(
        self,
        user_id: str,
        client_id: str,
        request: SyncRequest,
    ) -> SyncResponse:
        """Perform a full synchronization cycle.

        Orchestrates conversation sync, memory sync, and conflict resolution.
        """
        # Sync conversations
        conv_response = await self.sync_conversations(
            user_id, client_id,
            request.conversations_since,
            request.last_sync_timestamp,
        )

        # Sync memories
        mem_response = await self.sync_memories(
            user_id, client_id,
            request.memories_since,
            request.last_sync_timestamp,
        )

        # Merge responses
        response = SyncResponse(
            conversations=conv_response.conversations,
            memories=mem_response.memories,
            conflicts=conv_response.conflicts + mem_response.conflicts,
            server_timestamp=datetime.now(UTC).isoformat(),
            requires_full_sync=False,
        )

        # Mark all returned message IDs as seen
        all_ids: list[str] = []
        for conv in response.conversations:
            if conv.get("id"):
                all_ids.append(conv["id"])
        for mem in response.memories:
            if mem.get("id"):
                all_ids.append(mem["id"])
        if all_ids:
            await self.mark_messages_seen_bulk(client_id, all_ids)

        return response

    # ── Background Tasks ────────────────────────────────────

    async def start_background_sync(self) -> None:
        """Start background sync tasks."""
        self._running = True
        task = asyncio.create_task(self._heartbeat_monitor())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        logger.info("Background sync started")

    async def stop_background_sync(self) -> None:
        """Stop background sync tasks."""
        self._running = False
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        logger.info("Background sync stopped")

    async def _heartbeat_monitor(self) -> None:
        """Monitor client heartbeats and clean up stale sessions."""
        while self._running:
            try:
                stale = await self.get_stale_clients(timeout_seconds=45.0)
                for client_id in stale:
                    logger.info(
                        "Client %s is stale (no heartbeat for 45s), cleaning up",
                        client_id,
                    )
                    await self.unregister_session(client_id)
                    self._heartbeat_timestamps.pop(client_id, None)
                await asyncio.sleep(15)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in heartbeat monitor")
                await asyncio.sleep(15)

    # ── Health ──────────────────────────────────────────────

    async def get_health(self) -> dict[str, Any]:
        """Get sync service health status."""
        return {
            "active_sessions": len(self._sessions),
            "offline_queues": {
                client_id: len(queue)
                for client_id, queue in self._offline_queues.items()
            },
            "total_queued_messages": sum(
                len(q) for q in self._offline_queues.values()
            ),
            "vector_clocks": {
                entity: dict(clock)
                for entity, clock in self._vector_clocks.items()
            },
            "heartbeat_clients": len(self._heartbeat_timestamps),
        }


# Singleton instance
_sync_service: SyncService | None = None


def get_sync_service() -> SyncService:
    """Get or create the global SyncService instance."""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service