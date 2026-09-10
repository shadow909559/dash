"""Persistence tests for the shared local SQLite store (services/local_store.py).

Two guarantees are tested per service:
1. Data written by one instance is visible to a *fresh* instance constructed
   against the same database file — the "backend restart" scenario.
2. Migrations are idempotent — reopening the store never re-applies or fails.
"""

from __future__ import annotations

import pytest

from dash_backend.services.local_store import LocalStore, open_store


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "persist_test.db"


def test_migration_idempotent(db_path):
    s1 = open_store(db_path)
    assert s1.table_count("schema_migrations") >= 1
    # Reopen many times — no error, no duplicate migration rows.
    for _ in range(3):
        open_store(db_path)
    rows = s1.query("SELECT version, COUNT(*) AS n FROM schema_migrations GROUP BY version")
    assert all(r["n"] == 1 for r in rows)


def test_migration_records_versions(db_path):
    from dash_backend.services.local_store import _MIGRATIONS

    s = open_store(db_path)
    applied = {r["version"] for r in s.query("SELECT version FROM schema_migrations")}
    assert applied == {v for v, _ in _MIGRATIONS}


def test_kv_helpers(db_path):
    s = open_store(db_path)
    s.kv_set("k", {"a": 1})
    assert s.kv_get("k") == {"a": 1}
    s.kv_set("k", {"b": 2})  # overwrite
    assert s.kv_get("k") == {"b": 2}
    assert s.kv_get("missing", "fallback") == "fallback"
    s.kv_del("k")
    assert s.kv_get("k", None) is None


def test_email_restart(db_path):
    from dash_backend.services.email_calendar import EmailService

    store = open_store(db_path)
    email = EmailService(store=store)
    acct = email.add_account("me@example.com", provider="imap", display_name="Work")["account"]
    email.receive_email("a@b.c", "Hello", "body text")

    fresh = EmailService(store=open_store(db_path))
    assert any(a["id"] == acct["id"] for a in fresh.list_accounts())
    assert any(m["subject"] == "Hello" for m in fresh.get_inbox())


def test_calendar_restart(db_path):
    from dash_backend.services.email_calendar import CalendarService

    store = open_store(db_path)
    cal = CalendarService(store=store)
    ev = cal.create_event("Standup", "2026-09-11T09:00:00Z", "2026-09-11T09:30:00Z")["event"]

    fresh = CalendarService(store=open_store(db_path))
    assert any(e["id"] == ev["id"] for e in fresh.get_events())


def test_browser_restart(db_path):
    from dash_backend.services.voice_browser import BrowserService

    store = open_store(db_path)
    svc = BrowserService(store=store)
    tab = svc.open_tab("https://example.com")["tab"]
    bm = svc.add_bookmark("https://example.com", "Example")["bookmark"]

    fresh = BrowserService(store=open_store(db_path))
    assert any(t["id"] == tab["id"] for t in fresh.get_tabs())
    assert any(b["id"] == bm["id"] for b in fresh.get_bookmarks())


def test_collaboration_restart(db_path):
    from dash_backend.services.collaboration import WorkspaceService, ActivityFeedService

    store = open_store(db_path)
    ws = WorkspaceService(store=store).create("Team Space", "owner_u")["workspace"]
    WorkspaceService(store=store).add_member(ws["id"], "member_u", "editor")
    ActivityFeedService(store=store).record("owner_u", "document_created", workspace_id=ws["id"])

    fresh_ws = WorkspaceService(store=open_store(db_path))
    assert ws["id"] in [w["id"] for w in fresh_ws.list_all()]
    assert any(m["user_id"] == "member_u" for m in fresh_ws.get_members(ws["id"]))
    fresh_feed = ActivityFeedService(store=open_store(db_path))
    assert any(e["action"] == "document_created" for e in fresh_feed.get_feed(workspace_id=ws["id"]))


def test_prompt_studio_restart(db_path):
    from dash_backend.services.advanced_ai import PromptStudio

    store = open_store(db_path)
    svc = PromptStudio(store=store)
    p = svc.create_prompt("My Prompt", "Do the thing", category="writing")["prompt"]

    fresh = PromptStudio(store=open_store(db_path))
    assert any(x["id"] == p["id"] for x in fresh.get_all())


def test_model_swap_restart(db_path):
    import json as _json

    from dash_backend.services.model_ensemble import ModelHotSwap

    store = open_store(db_path)
    svc = ModelHotSwap(store=store)
    result = svc.swap("openai/gpt-4o-mini")
    assert result["ok"], result

    fresh = ModelHotSwap(store=open_store(db_path))
    hist = fresh.get_history()
    assert hist, "swap history must survive restart"
    assert "gpt-4o-mini" in _json.dumps(hist)


def test_plugin_install_restart(db_path):
    from dash_backend.services.plugin_service import PluginRegistry

    store = open_store(db_path)
    svc = PluginRegistry(store=store)
    result = svc.install("plg_code_runner")
    assert result["ok"], result

    fresh = PluginRegistry(store=open_store(db_path))
    installed_ids = {p["id"] for p in fresh.get_installed()}
    assert "plg_code_runner" in installed_ids


def test_shortcuts_dnd_sounds_restart(db_path):
    from dash_backend.services.shortcuts_service import (
        ShortcutManager,
        DNDManager,
        NotificationSounds,
    )

    store = open_store(db_path)
    ShortcutManager(store=store).set_custom("chat.new", "Ctrl+Alt+N")
    dnd = DNDManager(store=store)
    dnd.toggle(True)
    dnd.set_schedule("23:00", "06:30")
    dnd.add_exception("approval")
    NotificationSounds(store=store).set_volume(0.33)

    assert ShortcutManager(store=open_store(db_path)).get_all()[0]["shortcut"] == "Ctrl+Alt+N"
    fresh_dnd = DNDManager(store=open_store(db_path))
    assert fresh_dnd.get_state()["enabled"] is True
    assert fresh_dnd.get_state()["schedule"]["start"] == "23:00"
    assert "approval" in fresh_dnd.get_state()["exceptions"]
    assert NotificationSounds(store=open_store(db_path)).get_settings()["volume"] == 0.33


def test_biometric_restart(db_path):
    from dash_backend.services.security_hardening import BiometricAuthService

    svc = BiometricAuthService(store=open_store(db_path))
    svc.enroll("u_persist", "Desk PC")
    svc._audit("u_persist", "verify", True)

    fresh = BiometricAuthService(store=open_store(db_path))
    assert fresh.get_status("u_persist")["enrolled"] is True
    assert any(a["event"] == "verify" for a in fresh.get_audit_log("u_persist"))


def test_biometric_revoke_removes_row(db_path):
    from dash_backend.services.security_hardening import BiometricAuthService

    store = open_store(db_path)
    svc = BiometricAuthService(store=store)
    svc.enroll("u_bye", "Old PC")
    svc.revoke("u_bye")
    fresh = BiometricAuthService(store=open_store(db_path))
    assert fresh.get_status("u_bye")["enrolled"] is False


def test_service_default_singleton_uses_shared_store(monkeypatch, tmp_path):
    """Constructing a service with no store arg must hit the shared file, not
    a per-service throwaway DB — otherwise 'persistence' silently does nothing."""
    db = tmp_path / "shared.db"
    monkeypatch.setenv("DASH_LOCAL_STORE", str(db))
    LocalStore._instances.clear()
    from dash_backend.services.email_calendar import EmailService

    svc = EmailService()  # no store passed — the production path
    svc.receive_email("x@y.z", "Persisted", "body")
    # Shared singleton file now holds the row.
    shared = LocalStore.instance()
    assert shared.table_count("emails") >= 1
    assert any(
        m["subject"] == "Persisted" for m in EmailService(store=open_store(db)).get_inbox()
    )
    LocalStore._instances.clear()
