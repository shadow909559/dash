"""Unified SQLite persistence layer for all DASH services.

Provides async database operations with auto-migration, connection pooling,
and a clean API for CRUD operations across all service modules.

Usage:
    from dash_backend.services.database import db

    # Auto-create tables on startup
    await db.initialize()

    # CRUD operations
    await db.insert("workflows", {"name": "deploy", "status": "active"})
    rows = await db.query("workflows", where="status = ?", params=("active",))
    await db.update("workflows", {"status": "paused"}, where="name = ?", params=("deploy",))
    await db.delete("workflows", where="name = ?", params=("deploy",))

    # Raw SQL
    rows = await db.execute("SELECT COUNT(*) FROM workflows WHERE status = ?", ("active",))

    # Export/import
    data = await db.export_table("workflows")
    await db.import_table("workflows", data)
"""
from __future__ import annotations

import aiosqlite
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import logging

logger = logging.getLogger(__name__)

# Default database path
_DEFAULT_DB = os.environ.get(
    "DASH_DB_PATH",
    str(Path.home() / ".dash" / "dash.db"),
)

# All table schemas for auto-migration
TABLES = {
    # ── Workflows ────────────────────────────────────────────────────────
    "workflows": """
        CREATE TABLE IF NOT EXISTS workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            nodes TEXT DEFAULT '[]',
            edges TEXT DEFAULT '[]',
            status TEXT DEFAULT 'draft',
            template TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "workflow_executions": """
        CREATE TABLE IF NOT EXISTS workflow_executions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            input_data TEXT DEFAULT '{}',
            output_data TEXT DEFAULT '{}',
            started_at TEXT NOT NULL,
            completed_at TEXT,
            error TEXT DEFAULT ''
        )
    """,
    "workflow_schedules": """
        CREATE TABLE IF NOT EXISTS workflow_schedules (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            trigger_type TEXT NOT NULL,
            trigger_config TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            last_run TEXT,
            next_run TEXT,
            created_at TEXT NOT NULL
        )
    """,

    # ── Plugins ──────────────────────────────────────────────────────────
    "plugins": """
        CREATE TABLE IF NOT EXISTS plugins (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            version TEXT DEFAULT '1.0.0',
            author TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            permissions TEXT DEFAULT '[]',
            config TEXT DEFAULT '{}',
            installed_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,

    # ── Knowledge Graph ──────────────────────────────────────────────────
    "kg_entities": """
        CREATE TABLE IF NOT EXISTS kg_entities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            properties TEXT DEFAULT '{}',
            source TEXT DEFAULT '',
            confidence REAL DEFAULT 1.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,
    "kg_edges": """
        CREATE TABLE IF NOT EXISTS kg_edges (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            target_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            weight REAL DEFAULT 1.0,
            properties TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        )
    """,

    # ── Conversation Branches ────────────────────────────────────────────
    "conv_branches": """
        CREATE TABLE IF NOT EXISTS conv_branches (
            id TEXT PRIMARY KEY,
            parent_id TEXT,
            conversation_id TEXT NOT NULL,
            fork_point INTEGER DEFAULT 0,
            name TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """,

    # ── Token Usage ──────────────────────────────────────────────────────
    "token_usage": """
        CREATE TABLE IF NOT EXISTS token_usage (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0.0,
            request_type TEXT DEFAULT 'chat',
            recorded_at TEXT NOT NULL
        )
    """,

    # ── Activity Log ─────────────────────────────────────────────────────
    "activity_log": """
        CREATE TABLE IF NOT EXISTS activity_log (
            id TEXT PRIMARY KEY,
            activity_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            score REAL DEFAULT 0.0,
            recorded_at TEXT NOT NULL
        )
    """,

    # ── Errors ───────────────────────────────────────────────────────────
    "error_log": """
        CREATE TABLE IF NOT EXISTS error_log (
            id TEXT PRIMARY KEY,
            service TEXT NOT NULL,
            error_type TEXT NOT NULL,
            message TEXT NOT NULL,
            traceback TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}',
            recorded_at TEXT NOT NULL
        )
    """,

    # ── Shortcuts ────────────────────────────────────────────────────────
    "shortcuts": """
        CREATE TABLE IF NOT EXISTS shortcuts (
            id TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            keys TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            enabled INTEGER DEFAULT 1,
            custom INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """,

    # ── Password Vault ───────────────────────────────────────────────────
    "vault_entries": """
        CREATE TABLE IF NOT EXISTS vault_entries (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            username TEXT DEFAULT '',
            password_encrypted TEXT NOT NULL,
            url TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            tags TEXT DEFAULT '[]',
            favorite INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,

    # ── 2FA ──────────────────────────────────────────────────────────────
    "tfa_secrets": """
        CREATE TABLE IF NOT EXISTS tfa_secrets (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            secret_encrypted TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """,

    # ── Email ────────────────────────────────────────────────────────────
    "email_accounts": """
        CREATE TABLE IF NOT EXISTS email_accounts (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            provider TEXT DEFAULT 'custom',
            imap_host TEXT DEFAULT '',
            imap_port INTEGER DEFAULT 993,
            smtp_host TEXT DEFAULT '',
            smtp_port INTEGER DEFAULT 587,
            username TEXT DEFAULT '',
            password_encrypted TEXT DEFAULT '',
            connected INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """,

    # ── Calendar ─────────────────────────────────────────────────────────
    "calendar_events": """
        CREATE TABLE IF NOT EXISTS calendar_events (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            start_time TEXT NOT NULL,
            end_time TEXT,
            all_day INTEGER DEFAULT 0,
            recurrence TEXT DEFAULT '',
            reminders TEXT DEFAULT '[]',
            calendar_id TEXT DEFAULT 'primary',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,

    # ── Contacts ─────────────────────────────────────────────────────────
    "contacts": """
        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            company TEXT DEFAULT '',
            role TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            avatar_url TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,

    # ── Bookmarks ────────────────────────────────────────────────────────
    "bookmarks": """
        CREATE TABLE IF NOT EXISTS bookmarks (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            favicon TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            folder TEXT DEFAULT '/',
            ai_summary TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """,

    # ── Reading List ─────────────────────────────────────────────────────
    "reading_list": """
        CREATE TABLE IF NOT EXISTS reading_list (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'unread',
            priority INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            estimated_read_time INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """,

    # ── Reminders ────────────────────────────────────────────────────────
    "reminders": """
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT,
            priority INTEGER DEFAULT 0,
            completed INTEGER DEFAULT 0,
            recurrence TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """,

    # ── Time Tracking ────────────────────────────────────────────────────
    "time_entries": """
        CREATE TABLE IF NOT EXISTS time_entries (
            id TEXT PRIMARY KEY,
            task TEXT NOT NULL,
            project TEXT DEFAULT '',
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration_seconds INTEGER DEFAULT 0,
            tags TEXT DEFAULT '[]',
            billable INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """,

    # ── Action Items ─────────────────────────────────────────────────────
    "action_items": """
        CREATE TABLE IF NOT EXISTS action_items (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            due_date TEXT,
            source TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """,

    # ── Sprints ──────────────────────────────────────────────────────────
    "sprints": """
        CREATE TABLE IF NOT EXISTS sprints (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            goal TEXT DEFAULT '',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT DEFAULT 'planned',
            created_at TEXT NOT NULL
        )
    """,
    "sprint_items": """
        CREATE TABLE IF NOT EXISTS sprint_items (
            id TEXT PRIMARY KEY,
            sprint_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'backlog',
            story_points INTEGER DEFAULT 0,
            assignee TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """,

    # ── Sessions ─────────────────────────────────────────────────────────
    "user_sessions": """
        CREATE TABLE IF NOT EXISTS user_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            device_info TEXT DEFAULT '{}',
            ip_address TEXT DEFAULT '',
            last_activity TEXT NOT NULL,
            created_at TEXT NOT NULL,
            revoked INTEGER DEFAULT 0,
            revoked_at TEXT
        )
    """,

    # ── Feature Flags ────────────────────────────────────────────────────
    "feature_flags": """
        CREATE TABLE IF NOT EXISTS feature_flags (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            enabled INTEGER DEFAULT 0,
            rollout_percentage INTEGER DEFAULT 0,
            conditions TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,

    # ── Meeting Notes ────────────────────────────────────────────────────
    "meeting_notes": """
        CREATE TABLE IF NOT EXISTS meeting_notes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            attendees TEXT DEFAULT '[]',
            agenda TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            action_items TEXT DEFAULT '[]',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """,

    # ── Clips (Clipboard History) ────────────────────────────────────────
    "clipboard_history": """
        CREATE TABLE IF NOT EXISTS clipboard_history (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            source_app TEXT DEFAULT '',
            pinned INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """,

    # ── Notifications ────────────────────────────────────────────────────
    "notification_routing": """
        CREATE TABLE IF NOT EXISTS notification_routing (
            id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            rule_type TEXT NOT NULL,
            rule_config TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """,

    # ── Exports ──────────────────────────────────────────────────────────
    "export_history": """
        CREATE TABLE IF NOT EXISTS export_history (
            id TEXT PRIMARY KEY,
            export_type TEXT NOT NULL,
            format TEXT NOT NULL,
            file_path TEXT DEFAULT '',
            size_bytes INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """,

    # ── Backups ──────────────────────────────────────────────────────────
    "backups": """
        CREATE TABLE IF NOT EXISTS backups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            size_bytes INTEGER DEFAULT 0,
            tables_included TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            notes TEXT DEFAULT ''
        )
    """,

    # ── Performance Metrics ──────────────────────────────────────────────
    "performance_metrics": """
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id TEXT PRIMARY KEY,
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT DEFAULT '',
            tags TEXT DEFAULT '{}',
            recorded_at TEXT NOT NULL
        )
    """,

    # ── Logs ─────────────────────────────────────────────────────────────
    "logs": """
        CREATE TABLE IF NOT EXISTS logs (
            id TEXT PRIMARY KEY,
            level TEXT NOT NULL,
            module TEXT NOT NULL,
            message TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            recorded_at TEXT NOT NULL
        )
    """,
}


class Database:
    """Async SQLite database with auto-migration and clean CRUD API."""

    def __init__(self, db_path: str = _DEFAULT_DB):
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Create database file and run all table migrations."""
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row

        # Enable WAL mode for better concurrent access
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")

        # Create all tables
        for table_name, schema in TABLES.items():
            await self._conn.execute(schema)
        await self._conn.commit()

        self._initialized = True
        logger.info("Database initialized at %s with %d tables", self._db_path, len(TABLES))

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            self._initialized = False

    def _ensure_initialized(self) -> None:
        if not self._initialized or not self._conn:
            raise RuntimeError("Database not initialized. Call await db.initialize() first.")

    # ── CRUD Operations ──────────────────────────────────────────────────

    async def insert(self, table: str, data: dict[str, Any]) -> str:
        """Insert a row and return its id."""
        self._ensure_initialized()
        now = datetime.now(timezone.utc).isoformat()
        if "id" not in data:
            import uuid
            data["id"] = str(uuid.uuid4())
        if "created_at" not in data:
            data["created_at"] = now
        if "updated_at" not in data:
            data["updated_at"] = now

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        await self._conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            list(data.values()),
        )
        await self._conn.commit()
        return data.get("id", "")

    async def query(
        self,
        table: str,
        where: str = "",
        params: tuple = (),
        order_by: str = "created_at DESC",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Query rows from a table."""
        self._ensure_initialized()
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        sql += f" LIMIT {limit} OFFSET {offset}"

        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get(self, table: str, record_id: str) -> Optional[dict[str, Any]]:
        """Get a single row by id."""
        self._ensure_initialized()
        cursor = await self._conn.execute(
            f"SELECT * FROM {table} WHERE id = ?", (record_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def update(
        self, table: str, data: dict[str, Any], where: str = "", params: tuple = ()
    ) -> int:
        """Update rows. Returns number of affected rows."""
        self._ensure_initialized()
        if "updated_at" not in data:
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

        set_clause = ", ".join(f"{k} = ?" for k in data.keys())
        sql = f"UPDATE {table} SET {set_clause}"
        if where:
            sql += f" WHERE {where}"

        cursor = await self._conn.execute(sql, list(data.values()) + list(params))
        await self._conn.commit()
        return cursor.rowcount

    async def delete(self, table: str, where: str = "", params: tuple = ()) -> int:
        """Delete rows. Returns number of deleted rows."""
        self._ensure_initialized()
        sql = f"DELETE FROM {table}"
        if where:
            sql += f" WHERE {where}"

        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor.rowcount

    async def count(self, table: str, where: str = "", params: tuple = ()) -> int:
        """Count rows in a table."""
        self._ensure_initialized()
        sql = f"SELECT COUNT(*) as cnt FROM {table}"
        if where:
            sql += f" WHERE {where}"
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def execute(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        """Execute raw SQL and return results."""
        self._ensure_initialized()
        cursor = await self._conn.execute(sql, params)
        try:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception:
            await self._conn.commit()
            return []

    async def execute_write(self, sql: str, params: tuple = ()) -> int:
        """Execute raw SQL for writes (INSERT/UPDATE/DELETE)."""
        self._ensure_initialized()
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor.rowcount

    # ── Export / Import ──────────────────────────────────────────────────

    async def export_table(self, table: str) -> list[dict[str, Any]]:
        """Export all rows from a table as JSON-serializable dicts."""
        return await self.query(table, limit=100000)

    async def import_table(self, table: str, rows: list[dict[str, Any]]) -> int:
        """Import rows into a table. Returns count imported."""
        count = 0
        for row in rows:
            await self.insert(table, row)
            count += 1
        return count

    async def export_all(self) -> dict[str, Any]:
        """Export all tables."""
        result = {}
        for table_name in TABLES:
            result[table_name] = await self.export_table(table_name)
        return result

    async def backup(self, backup_path: str) -> int:
        """Create a backup of the database."""
        self._ensure_initialized()
        await self._conn.execute(f"VACUUM INTO '{backup_path}'")
        return os.path.getsize(backup_path)

    # ── Schema Introspection ─────────────────────────────────────────────

    async def table_info(self, table: str) -> list[dict[str, Any]]:
        """Get column info for a table."""
        self._ensure_initialized()
        cursor = await self._conn.execute(f"PRAGMA table_info({table})")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def list_tables(self) -> list[str]:
        """List all tables."""
        self._ensure_initialized()
        cursor = await self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        rows = await cursor.fetchall()
        return [row["name"] for row in rows]


# Singleton instance
db = Database()
