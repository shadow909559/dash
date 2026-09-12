"""Shared local SQLite persistence for DASH feature services.

One database file (``%LOCALAPPDATA%\\DASH\\dash_local.db``, override with
``DASH_LOCAL_STORE``) backs every feature service that previously lived
only in memory. Design (decisions.md #36):

- Versioned migrations: a ``schema_migrations`` table records applied
  versions; pending migrations run inside a transaction the first time a
  service connects — i.e. at backend startup when the singletons import.
  Re-running is a no-op (idempotent).
- Document rows: services persist JSON payloads in per-service tables
  (``id TEXT PRIMARY KEY, data TEXT``) so the existing dict-shaped
  service code keeps its exact in-memory semantics while gaining
  durability. Lists are derived from ``SELECT``s ordered by ``seq``.
- WAL mode + short transactions: services are read-heavy singletons on
  one event loop; WAL keeps concurrent reads cheap.
- Thread-safety: one connection per store instance guarded by an RLock,
  matching the access patterns of the service singletons (FastAPI runs
  sync route bodies on a worker pool, so a lock is required).
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

# DASH_LOCAL_STORE overrides the whole path (file). Empty string or
# "memory" selects an in-memory database (used by tests that don't care).
_DEFAULT_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")


def default_db_path() -> Path:
    override = os.environ.get("DASH_LOCAL_STORE")
    if override:
        if override in ("", "memory"):
            return Path(":memory:")
        return Path(override)
    return _DEFAULT_DIR / "DASH" / "dash_local.db"


def new_id(prefix: str) -> str:
    """Stable, collision-free id: prefix_<12 hex>. Length-derived ids
    (email_0, ws_1) collide once data survives restarts."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ── Schema migrations ──────────────────────────────────────────────────────
# Each entry: (version, list of SQL statements). Append-only; never edit an
# applied migration — add a new one.

_MIGRATIONS: list[tuple[int, list[str]]] = [
    (
        1,
        [
            # Email/calendar/contacts (email_calendar.py)
            """CREATE TABLE IF NOT EXISTS email_accounts (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS emails (
                id TEXT PRIMARY KEY, seq INTEGER, folder TEXT DEFAULT 'inbox', data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS email_rules (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS calendars (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS calendar_events (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS calendar_reminders (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS contacts (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS contact_groups (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            # Voice/browser (voice_browser.py)
            """CREATE TABLE IF NOT EXISTS voice_memos (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS voice_custom_commands (
                id TEXT PRIMARY KEY, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS browser_tabs (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS browser_bookmarks (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS browser_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS browser_summaries (
                tab_id TEXT PRIMARY KEY, data TEXT NOT NULL)""",
            # Collaboration (collaboration.py)
            """CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT, user_id TEXT, data TEXT NOT NULL,
                PRIMARY KEY (workspace_id, user_id))""",
            """CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY, seq INTEGER, entity_type TEXT, entity_id TEXT, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS activity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id TEXT, user_id TEXT, data TEXT NOT NULL)""",
            # Prompt studio / evaluation / learning (advanced_ai.py)
            """CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS prompt_evaluations (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS learning_skills (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS learning_corrections (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
            # Model hot-swap history (model_ensemble.py)
            """CREATE TABLE IF NOT EXISTS model_swap_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL)""",
            # Plugin install state (plugin_service.py)
            """CREATE TABLE IF NOT EXISTS plugin_installs (
                plugin_id TEXT PRIMARY KEY, enabled INTEGER, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS plugin_ratings (
                plugin_id TEXT PRIMARY KEY, data TEXT NOT NULL)""",
            # Settings (shortcuts_service.py): custom shortcuts, sounds, DND
            """CREATE TABLE IF NOT EXISTS kv_settings (
                key TEXT PRIMARY KEY, data TEXT NOT NULL)""",
            # Biometric (security_hardening.py): enrollments + audit trail
            """CREATE TABLE IF NOT EXISTS biometric_enrollments (
                user_id TEXT PRIMARY KEY, data TEXT NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS biometric_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, data TEXT NOT NULL)""",
            """CREATE INDEX IF NOT EXISTS idx_emails_folder ON emails(folder)""",
            """CREATE INDEX IF NOT EXISTS idx_comments_entity ON comments(entity_type, entity_id)""",
            """CREATE INDEX IF NOT EXISTS idx_activity_ws ON activity_events(workspace_id)""",
        ],
    ),
    (
        2,
        [
            # Unified deadlines (email_calendar_sync.py): fed from email scans,
            # calendar deadline events, and manual entries.
            """CREATE TABLE IF NOT EXISTS deadlines (
                id TEXT PRIMARY KEY, seq INTEGER, data TEXT NOT NULL)""",
        ],
    ),
]


class LocalStore:
    """Small synchronous SQLite wrapper with auto-migration."""

    _instances: dict[str, "LocalStore"] = {}
    _class_lock = threading.Lock()

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._path = db_path or default_db_path()
        self._lock = threading.RLock()
        self._conn: Optional[sqlite3.Connection] = None
        self._open()

    @classmethod
    def instance(cls) -> "LocalStore":
        """Process-wide shared store (one file, one connection)."""
        key = str(default_db_path())
        with cls._class_lock:
            if key not in cls._instances:
                cls._instances[key] = LocalStore()
            return cls._instances[key]

    def _open(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._migrate()

    def _migrate(self) -> None:
        """Apply pending migrations inside a transaction; no-op when current."""
        assert self._conn is not None
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            row["version"]
            for row in self._conn.execute("SELECT version FROM schema_migrations")
        }
        for version, statements in _MIGRATIONS:
            if version in applied:
                continue
            try:
                with self._conn:
                    for stmt in statements:
                        self._conn.execute(stmt)
                    self._conn.execute(
                        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                        (version, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
                    )
                logger.info("Local store migrated to version %d", version)
            except sqlite3.OperationalError:
                # Two processes racing startup: another one applied it first.
                logger.debug("Migration %d already applied concurrently", version)
                self._conn.rollback()

    # ── Document helpers ────────────────────────────────────────────

    def execute(self, sql: str, params: Iterable[Any] = ()) -> None:
        with self._lock:
            assert self._conn is not None
            self._conn.execute(sql, tuple(params))
            self._conn.commit()

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[dict]:
        with self._lock:
            assert self._conn is not None
            rows = self._conn.execute(sql, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    def put_doc(self, table: str, doc_id: str, data: dict, seq: Optional[int] = None) -> None:
        self.execute(
            f"INSERT INTO {table} (id, seq, data) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET data = excluded.data, seq = COALESCE(excluded.seq, seq)",
            (doc_id, seq, json.dumps(data)),
        )

    def delete_doc(self, table: str, doc_id: str) -> None:
        self.execute(f"DELETE FROM {table} WHERE id = ?", (doc_id,))

    def list_docs(self, table: str, limit: Optional[int] = None, newest_first: bool = False) -> list[dict]:
        order = "seq DESC" if newest_first else "seq ASC"
        sql = f"SELECT data FROM {table} ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [json.loads(r["data"]) for r in self.query(sql)]

    def next_seq(self, table: str) -> int:
        row = self.query(f"SELECT COALESCE(MAX(seq), 0) + 1 AS n FROM {table}")
        return int(row[0]["n"])

    # Test/diagnostic helper
    def table_count(self, table: str) -> int:
        try:
            row = self.query(f"SELECT COUNT(*) AS n FROM {table}")
            return int(row[0]["n"])
        except sqlite3.OperationalError:
            return 0

    # ── Key-value helpers (kv_settings table) ───────────────────────

    def kv_get(self, key: str, default: Any = None) -> Any:
        rows = self.query("SELECT data FROM kv_settings WHERE key = ?", (key,))
        return json.loads(rows[0]["data"]) if rows else default

    def kv_set(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO kv_settings (key, data) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (key, json.dumps(value)),
        )

    def kv_del(self, key: str) -> None:
        self.execute("DELETE FROM kv_settings WHERE key = ?", (key,))


def open_store(db_path: Optional[Path] = None) -> LocalStore:
    """Explicit-path store (tests); the shared instance for services."""
    if db_path is None:
        return LocalStore.instance()
    return LocalStore(db_path)
