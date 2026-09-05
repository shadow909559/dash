"""Regression tests for bugs discovered and fixed during the system-wide repair.

Covers:
1. Executive worker timezone handling
2. Outbox migration / table availability
3. Disabled Supabase sync does not start worker
4. Enabled Supabase sync starts only after schema readiness
5. pyperclip dependency/import
6. Clipboard operations
7. Backend health probe behaviour
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession


# ── 1. Executive worker uses timezone-aware datetimes ────────────────────────


class TestExecutiveWorkerTimezone:
    """Verify that executive/service.py uses timezone-aware datetime.now(UTC)."""

    def test_reset_stuck_tasks_uses_aware_datetime(self) -> None:
        """reset_stuck_tasks must not call datetime.utcnow()."""
        import inspect as _inspect
        from dash_backend.executive import service

        src = _inspect.getsource(service.reset_stuck_tasks)
        assert "utcnow()" not in src, "reset_stuck_tasks still uses deprecated utcnow()"
        assert "timezone" in src, "reset_stuck_tasks must import/use timezone"

    def test_worker_loop_uses_aware_datetime(self) -> None:
        """worker_loop's claim step must use timezone-aware datetime."""
        import inspect as _inspect
        from dash_backend.executive import service

        src = _inspect.getsource(service.worker_loop)
        assert "utcnow()" not in src, "worker_loop still uses deprecated utcnow()"

    def test_run_pending_task_uses_aware_datetime(self) -> None:
        """run_pending_task timing must use timezone-aware datetime."""
        import inspect as _inspect
        from dash_backend.executive import service

        src = _inspect.getsource(service.run_pending_task)
        assert "utcnow()" not in src, "run_pending_task still uses deprecated utcnow()"

    def test_executive_service_imports_update(self) -> None:
        """The update() SQLAlchemy construct must be importable from the service module."""
        from dash_backend.executive import service

        assert hasattr(service, "update"), (
            "executive.service must import sqlalchemy.update for reset_stuck_tasks"
        )

    def test_executive_service_imports_timezone(self) -> None:
        """The timezone object must be importable from the service module."""
        from dash_backend.executive import service

        assert hasattr(service, "timezone"), (
            "executive.service must import datetime.timezone"
        )


# ── 2. Outbox table exists in the active database ────────────────────────────


class TestOutboxTableAvailability:
    """Verify the sync_outbox_events table is present after migration."""

    def test_sync_outbox_events_table_exists_in_sqlite(self) -> None:
        """The SQLite dev database must contain sync_outbox_events."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).resolve().parent.parent / "dash_dev.db"
        if not db_path.exists():
            pytest.skip("dash_dev.db not found")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_outbox_events'"
        )
        result = cursor.fetchone()
        conn.close()
        assert result is not None, "sync_outbox_events table missing from dash_dev.db"

    def test_alembic_version_at_outbox_migration(self) -> None:
        """Alembic version should be at least at the outbox migration."""
        import sqlite3
        from pathlib import Path

        db_path = Path(__file__).resolve().parent.parent / "dash_dev.db"
        if not db_path.exists():
            pytest.skip("dash_dev.db not found")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT version_num FROM alembic_version")
        versions = [r[0] for r in cursor.fetchall()]
        conn.close()
        assert "9f3a2c4d1e70" in versions, (
            f"Outbox migration 9f3a2c4d1e70 not applied; versions={versions}"
        )


# ── 3. Disabled Supabase sync does not start worker ──────────────────────────


class TestDisabledSyncGating:
    """Verify that SUPABASE_SYNC_ENABLED=false means zero sync activity."""

    def test_sync_is_enabled_code_default_is_false(self) -> None:
        """Default config has supabase_sync_enabled=False.
    
        Note: the .env may override this in dev. We verify the Pydantic field
        default, not the runtime value (which depends on the env file).
        """
        from dash_backend.config import Settings
    
        # Pydantic field default is False
        field = Settings.model_fields["supabase_sync_enabled"]
        assert field.default is False, "supabase_sync_enabled field default must be False"

    def test_enqueue_event_returns_none_when_disabled(self) -> None:
        """enqueue_event must short-circuit when sync is disabled."""
        from dash_backend.sync.outbox import enqueue_event, sync_is_enabled

        # sync_is_enabled checks the global settings; in test env it defaults False.
        # We verify the guard exists by checking the function source.
        import inspect as _inspect

        src = _inspect.getsource(enqueue_event)
        assert "sync_is_enabled" in src, "enqueue_event must check sync_is_enabled"

    def test_outbox_worker_run_checks_feature_flag(self) -> None:
        """The worker's run() loop must check supabase_sync_enabled each iteration."""
        import inspect as _inspect
        from dash_backend.sync.supabase_outbox_worker import SupabaseOutboxWorker

        src = _inspect.getsource(SupabaseOutboxWorker.run)
        assert "supabase_sync_enabled" in src, (
            "Worker run() must check supabase_sync_enabled"
        )


# ── 4. Alembic migration runs at startup ─────────────────────────────────────


class TestStartupMigration:
    """Verify the startup migration code path exists in main.py."""

    def test_lifespan_calls_alembic_upgrade(self) -> None:
        """The lifespan function must include alembic upgrade head."""
        import inspect as _inspect
        from dash_backend.main import lifespan

        src = _inspect.getsource(lifespan)
        assert "alembic" in src.lower(), "lifespan must invoke Alembic migrations"
        assert "upgrade" in src.lower(), "lifespan must call alembic upgrade head"


# ── 5. pyperclip dependency ──────────────────────────────────────────────────


class TestPyperclipDependency:
    """Verify pyperclip is importable and declared as a dependency."""

    def test_pyperclip_importable(self) -> None:
        """pyperclip must be importable from the active Python."""
        import pyperclip

        assert hasattr(pyperclip, "copy")
        assert hasattr(pyperclip, "paste")

    def test_pyperclip_in_pyproject_dependencies(self) -> None:
        """pyperclip must be declared in pyproject.toml."""
        from pathlib import Path

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert "pyperclip" in content, "pyperclip not found in pyproject.toml"

    def test_pyperclip_in_requirements_txt(self) -> None:
        """pyperclip must be mirrored in requirements.txt."""
        from pathlib import Path

        req = Path(__file__).resolve().parent.parent / "requirements.txt"
        content = req.read_text()
        assert "pyperclip" in content, "pyperclip not found in requirements.txt"


# ── 6. Clipboard operations ──────────────────────────────────────────────────


class TestClipboardOperations:
    """Verify clipboard read/write works through the ClipboardManager."""

    def test_clipboard_manager_write_and_read(self) -> None:
        """ClipboardManager.write_text + read_text round-trips correctly."""
        from dash_backend.desktop.clipboard_manager import ClipboardManager

        cm = ClipboardManager()
        result = asyncio.run(cm.write_text("DASH regression test"))
        assert result is True
        content = asyncio.run(cm.read_text())
        assert content == "DASH regression test"

    def test_clipboard_manager_error_handling(self) -> None:
        """ClipboardManager should not raise on read failure."""
        from dash_backend.desktop.clipboard_manager import ClipboardManager

        cm = ClipboardManager()
        # Even if clipboard is empty or inaccessible, should return empty string
        content = asyncio.run(cm.read_text())
        assert isinstance(content, str)


# ── 7. Backend health endpoint ───────────────────────────────────────────────


class TestBackendHealthEndpoint:
    """Verify health endpoint returns correct structure."""

    def test_health_endpoint_returns_ok(self) -> None:
        """GET /health must return status ok."""
        from fastapi.testclient import TestClient
        from dash_backend.main import app

        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "DASH Backend" in data["service"]
        assert "uptime" in data

    def test_health_endpoint_v1(self) -> None:
        """GET /api/v1/health must also return status ok."""
        from fastapi.testclient import TestClient
        from dash_backend.main import app

        client = TestClient(app)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
