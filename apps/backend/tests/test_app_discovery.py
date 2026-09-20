"""App-discovery fixes (#134) — the "installed apps not showing" report.

Real-machine diagnosis before the fix (the honest way to build these pins):
    resolve('dash')     -> AutoHotkey Dash   (alphabetical tie-break bug)
    display names       -> "Freebuff 0.0.127" (installer version suffixes)
    cache               -> never expires, so post-boot installs never appear
    path ranking        -> sort was INVERTED, path-less stubs preferred

All tests stub the three scans — no dependence on THIS machine's installs.
"""

from __future__ import annotations

import pytest

from dash_backend.services.application_discovery import (
    ApplicationDiscoveryService,
    get_application_discovery,
)


def _make_service(monkeypatch, registry: list[dict], shortcuts: list[dict] | None = None,
                  program_files: list[dict] | None = None) -> ApplicationDiscoveryService:
    svc = ApplicationDiscoveryService()
    monkeypatch.setattr(svc, "_scan_registry", lambda: list(registry))
    monkeypatch.setattr(svc, "_scan_shortcuts", lambda: list(shortcuts or []))
    monkeypatch.setattr(svc, "_scan_program_files", lambda: list(program_files or []))
    return svc


@pytest.fixture(autouse=True)
def _fresh_singleton():
    """The service is a Singleton — tests must not share cached discovery
    state (or stubbed scan methods) across cases."""
    from dash_backend.services.singleton import SingletonMeta
    SingletonMeta._instances.pop(ApplicationDiscoveryService, None)
    yield
    SingletonMeta._instances.pop(ApplicationDiscoveryService, None)


# ── name cleaning ────────────────────────────────────────────────────


def test_clean_name_strips_versions():
    f = ApplicationDiscoveryService._clean_name
    assert f("Freebuff 0.0.127") == "Freebuff"
    assert f("DASH 1.0.0") == "DASH"
    assert f("Some App v2.3.1 (x64)") == "Some App"
    assert f("Visual Studio Code") == "Visual Studio Code"  # untouched


# ── collision ranking ────────────────────────────────────────────────


def test_dash_resolves_to_dash_not_autohotkey(monkeypatch):
    svc = _make_service(monkeypatch, registry=[
        {"name": "DASH 1.0.0", "path": "C:\\Program Files\\DASH\\DASH.exe",
         "source": "registry", "aliases": []},
        {"name": "AutoHotkey Dash", "path": "C:\\x\\AutoHotkey Dash.lnk",
         "source": "shortcut", "aliases": []},
    ])
    app = svc.resolve("dash")
    assert app is not None
    assert app["path"] == "C:\\Program Files\\DASH\\DASH.exe"


def test_freebuff_resolves_to_freebuff_exe(monkeypatch):
    svc = _make_service(monkeypatch, registry=[
        {"name": "Freebuff 0.0.127",
         "path": "C:\\Users\\x\\AppData\\Local\\Programs\\@codebufffreebuff-desktop\\Freebuff.exe",
         "source": "registry", "aliases": []},
    ])
    app = svc.resolve("freebuff")
    assert app is not None
    assert app["path"].endswith("Freebuff.exe")


def test_pathless_registry_stub_loses_to_real_executable(monkeypatch):
    svc = _make_service(monkeypatch, registry=[
        {"name": "Dash Report", "path": "", "source": "registry", "aliases": []},
        {"name": "DASH", "path": "C:\\Program Files\\DASH\\DASH.exe",
         "source": "registry", "aliases": []},
    ])
    app = svc.resolve("dash")
    assert app["path"] != ""


# ── substring-search ranking (previously inverted) ──────────────────


def test_substring_search_prefers_pathed_exact_match(monkeypatch):
    svc = _make_service(monkeypatch, registry=[
        {"name": "DASH Helper", "path": "", "source": "registry", "aliases": []},
        {"name": "DASH 1.0.0", "path": "C:\\Program Files\\DASH\\DASH.exe",
         "source": "registry", "aliases": []},
    ])
    results = svc.search("dash")
    assert results, "search must find the app"
    assert results[0]["path"] == "C:\\Program Files\\DASH\\DASH.exe"


# ── TTL cache (#134 core fix) ────────────────────────────────────────


def test_newly_installed_app_appears_without_rebuild(monkeypatch):
    """An app installed after the first scan must appear once the TTL
    expires — previously the cache was forever, so the app 'never showed'
    until a backend restart."""
    registry: list[dict] = [
        {"name": "Chrome", "path": "C:\\Program Files\\Chrome\\chrome.exe",
         "source": "registry", "aliases": []},
    ]
    svc = _make_service(monkeypatch, registry)
    svc.CACHE_TTL_S = 60.0
    assert svc.resolve("chrome") is not None
    assert svc.resolve("freebuff") is None  # not installed yet

    # The user installs Freebuff while DASH keeps running.
    registry.append({
        "name": "Freebuff 0.0.127",
        "path": "C:\\Users\\x\\AppData\\Local\\Programs\\@codebufffreebuff-desktop\\Freebuff.exe",
        "source": "registry", "aliases": [],
    })
    assert svc.resolve("freebuff") is None  # inside TTL: cached (throttled)
    svc._cache_at -= svc.CACHE_TTL_S + 1.0  # simulate time passing
    assert svc.resolve("freebuff") is not None  # TTL expired: rescan finds it


def test_forced_refresh_bypasses_cache(monkeypatch):
    calls = {"n": 0}

    def scan():
        calls["n"] += 1
        return [{"name": "DASH", "path": "C:\\Program Files\\DASH\\DASH.exe",
                 "source": "registry", "aliases": []}]

    svc = ApplicationDiscoveryService()
    monkeypatch.setattr(svc, "_scan_registry", scan)
    monkeypatch.setattr(svc, "_scan_shortcuts", lambda: [])
    monkeypatch.setattr(svc, "_scan_program_files", lambda: [])
    svc.discover_all(refresh=True)
    svc.discover_all(refresh=True)
    assert calls["n"] == 2


# ── aliases ──────────────────────────────────────────────────────────


def test_dash_and_freebuff_aliases_registered():
    aliases = ApplicationDiscoveryService.KNOWN_ALIASES
    assert "dash" in aliases and "freebuff" in aliases
