"""CORS localhost-dev preflight tests (decisions.md #75).

The gap found in live testing: boots that pin explicit origins (every
boot script, prod) answered preflights from a drifted dev-server port
with 400 — vite moves (5173 → 5174) and the browser blocks every call.

The fix: when `cors_localhost_dev` is on (default), any http(s)
localhost / 127.0.0.1 origin on ANY port passes the preflight, with the
request origin REFLECTED (not "*") so credentialed requests work —
browsers reject a literal "*" alongside credentials=True. Remote origins
are still governed strictly by DASH_CORS_ORIGINS_RAW, and
DASH_CORS_LOCALHOST_DEV=0 restores the strict allow-list.

Every test builds the REAL app via create_app() with the REAL middleware
chain — no CORS approximation. get_settings() is lru_cached, so each
test clears the cache before AND after (the after-clear keeps other test
files from inheriting this file's env).
"""
from __future__ import annotations

import pytest


def _client(env: dict[str, str]):
    """create_app() with the given env; returns (client, cleanup)."""
    import os

    from fastapi.testclient import TestClient

    from dash_backend.config import get_settings
    from dash_backend.main import create_app

    old = {k: os.environ.get(k) for k in env}
    try:
        os.environ.update(env)
        get_settings.cache_clear()
        app = create_app()
        from dash_backend.auth.dependencies import get_current_user

        app.dependency_overrides[get_current_user] = lambda: {"sub": "t"}
        return TestClient(app)
    finally:
        get_settings.cache_clear()
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _preflight(client, origin: str, path: str = "/api/v1/vision/watch/config"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )


@pytest.fixture(scope="module", autouse=True)
def _settings_cache_hygiene():
    """Module-level belt-and-braces: the cache must be cold on entry and
    cleared on exit so later test files see their own env."""
    from dash_backend.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestLocalhostDevPreflight:
    def test_preflight_from_any_localhost_port_succeeds(self) -> None:
        """THE regression test: explicit pinned origins in the boot env,
        preflight from any localhost port → 200 with reflected origin."""
        client = _client(
            {
                "DASH_CORS_ORIGINS_RAW": "http://localhost:5188",
                "DASH_CORS_LOCALHOST_DEV": "1",
            }
        )
        for origin in (
            "http://localhost:5173",   # vite default
            "http://localhost:5174",   # vite drifted (the live-test failure)
            "http://localhost:5188",   # pinned origin itself
            "http://localhost:5199",   # any other port
            "http://127.0.0.1:3000",   # loopback IP, explicit port
            "http://127.0.0.1",        # loopback IP, default port
            "https://localhost:5188",  # https dev servers
        ):
            r = _preflight(client, origin)
            assert r.status_code == 200, f"{origin} → {r.status_code}"
            assert (
                r.headers.get("access-control-allow-origin") == origin
            ), f"{origin}: origin must be reflected, not '*'"
            assert r.headers.get("access-control-allow-credentials") == "true"
            assert "authorization" in r.headers.get(
                "access-control-allow-headers", ""
            ).lower()

    def test_actual_request_carries_reflected_origin_and_credentials(self) -> None:
        """Preflight is only half the handshake: the actual request must
        echo the origin (credentials made '*' illegal) and ACAC=true."""
        client = _client(
            {
                "DASH_CORS_ORIGINS_RAW": "http://localhost:5188",
            }
        )
        r = client.get(
            "/api/v1/vision/status",
            headers={"Origin": "http://localhost:5174"},
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5174"
        assert r.headers.get("access-control-allow-credentials") == "true"

    def test_non_localhost_origins_still_denied(self) -> None:
        """The regex is a localhost convenience — it must not open the API
        to remote hosts or localhost lookalikes."""
        client = _client({"DASH_CORS_ORIGINS_RAW": "http://localhost:5188"})
        for origin in (
            "http://evil.com",
            "http://localhost.evil.com",  # localhost in a HOST header sense
            "https://example.com",
            "http://192.168.1.50:5173",   # LAN machine, not loopback
            "http://localhost:5173.evil.com",
        ):
            r = _preflight(client, origin)
            assert r.status_code == 400, f"{origin} must be denied"

    def test_remote_explicit_origin_still_allowed_via_list(self) -> None:
        """The existing mechanism is untouched: an explicit origin from the
        list (e.g. the Tauri/emulator host) still preflights fine."""
        client = _client(
            {
                "DASH_CORS_ORIGINS_RAW": "http://localhost:5188,https://dash-backend.fly.dev",
            }
        )
        r = _preflight(client, "https://dash-backend.fly.dev")
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "https://dash-backend.fly.dev"

    def test_kill_switch_restores_strict_allow_list(self) -> None:
        """DASH_CORS_LOCALHOST_DEV=0: drifted ports are denied again, the
        pinned origin still works — the old behavior, on demand."""
        client = _client(
            {
                "DASH_CORS_ORIGINS_RAW": "http://localhost:5188",
                "DASH_CORS_LOCALHOST_DEV": "0",
            }
        )
        r = _preflight(client, "http://localhost:5174")
        assert r.status_code == 400
        r = _preflight(client, "http://localhost:5188")
        assert r.status_code == 200

    def test_default_wildcard_still_works_with_credentials(self) -> None:
        """The shipped default env includes '*' — with starlette's
        reflect-on-credentials behavior that answers preflights for any
        origin; this pins that the default didn't regress."""
        client = _client({"DASH_CORS_ORIGINS_RAW": "*"})
        r = _preflight(client, "http://localhost:5173")
        assert r.status_code == 200

    def test_preflight_on_unauth_path(self) -> None:
        """Health-style route: same middleware, preflight still answers."""
        client = _client({"DASH_CORS_ORIGINS_RAW": "http://localhost:5188"})
        r = _preflight(client, "http://localhost:5174", path="/api/v1/health")
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:5174"
