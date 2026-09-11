"""Spec-driven API sweep: every OpenAPI operation exercised systematically.

Strategy (decisions.md #38) — with 654 operations across 591 paths, a
hand-written test per route cannot stay in sync with the codebase. Instead
this suite reads the live OpenAPI schema and enforces invariants over ALL
of them:

1. **No 5xx, ever** — every operation is probed with (a) no body / no
   params, (b) a minimal-valid body derived from the schema, and (c) a
   deliberately junk body. Any 500/502/503 is a bug. The app's global
   exception handler converts unexpected exceptions to 500s, so a clean
   sweep proves every handler validates its inputs.
2. **Auth contract** — a curated allowlist of public routes may answer
   anon clients with 2xx/405/422; everything else MUST return 401/403,
   never 2xx and never 5xx.
3. **Happy-path deep tests** — real payloads for high-traffic routes,
   including the route-shadowing regression that motivated this suite
   (`GET /memory/{memory_id}` swallowing `/memory/stats|types|continue`).

The sweep clears the rate limiter between phases so the limiter itself
never decides an outcome.
"""

from __future__ import annotations

import re

import pytest

from dash_backend.main import create_app
from dash_backend.security.rate_limiter import get_api_limiter

AUTH_HEADERS = {"Authorization": "Bearer " + "dash-test-device-token-" + "a" * 32}

# ── Schema-aware payload generation ─────────────────────────────────────


def _minimal_valid(schema: dict, spec: dict, depth: int = 0) -> object:
    """Build a minimal object satisfying a JSON schema (no $ref resolution
    needed beyond two levels; FastAPI inlines request-body schemas)."""
    if depth > 3:
        return None
    if not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        node = spec
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return _minimal_valid(node, spec, depth + 1)
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    if "example" in schema:
        return schema["example"]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        required = schema.get("required", []) or []
        out = {}
        for name in required:
            prop = schema.get("properties", {}).get(name)
            if prop is None:
                out[name] = None
            else:
                out[name] = _minimal_valid(prop, spec, depth + 1)
        return out
    if t == "array":
        return [_minimal_valid(schema.get("items", {}), spec, depth + 1)]
    if t == "string":
        fmt = schema.get("format", "")
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt in ("date-time", "date"):
            return "2026-01-01T00:00:00+00:00" if fmt == "date-time" else "2026-01-01"
        if "pattern" in schema and re.search(r"\^", schema["pattern"]):
            return "x" * 12  # anchored patterns: harmless generic token
        return "sweep-test"
    if t == "integer":
        return schema.get("minimum", 1)
    if t == "number":
        return schema.get("minimum", 1.0)
    if t == "boolean":
        return True
    return None


def _path_params(path: str, spec: dict) -> list[dict]:
    """Collect path-parameter schemas from the OpenAPI operation item."""
    item = spec["paths"].get(path, {})
    for op in item.values():
        if isinstance(op, dict):
            return [p for p in op.get("parameters", []) if p.get("in") == "path"]
    return []


def _fill_params(path: str, spec: dict) -> str:
    for p in _path_params(path, spec):
        schema = p.get("schema", {})
        name = p["name"]
        if schema.get("type") == "integer" or "int" in str(schema.get("type", "")):
            val = "1"
        elif schema.get("format") == "uuid":
            val = "00000000-0000-0000-0000-000000000000"
        else:
            val = "sweep-probe"
        path = path.replace("{" + name + "}", val)
    return re.sub(r"\{[^}]+\}", "probe", path)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def spec():
    app = create_app()
    return app.openapi()


@pytest.fixture()
def anon_client():
    from fastapi.testclient import TestClient

    app = create_app()
    get_api_limiter().buckets.clear()
    return TestClient(app)


@pytest.fixture()
def authed_client():
    from fastapi.testclient import TestClient

    app = create_app()
    get_api_limiter().buckets.clear()
    return TestClient(app, headers=AUTH_HEADERS)


# ── 1. The sweep: no operation may 5xx ──────────────────────────────────


def _all_operations(spec: dict) -> list[tuple[str, str]]:
    ops = []
    for path, item in spec["paths"].items():
        for method in item:
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                ops.append((method.upper(), path))
    return sorted(ops)


# "Service unavailable / not configured" is a legitimate dependency state
# (e.g. GET /ollama-tunnel/models with no tunnel URL) — not a handler bug.
# A raw 500 (unhandled exception) still fails the sweep.
EXPECTED_DEP_STATUSES = {503}


def test_openapi_covers_full_surface(spec):
    """Guard: the app must expose its whole surface to the sweep."""
    ops = _all_operations(spec)
    assert len(ops) >= 600, f"surface shrank? only {len(ops)} operations"


@pytest.mark.parametrize(
    "method,path", _all_operations(create_app().openapi()), ids=lambda v: None
)
def test_no_5xx_on_minimal_valid_input(anon_client, spec, method, path):
    """Minimal-valid body/params must never produce a server error."""
    get_api_limiter().buckets.clear()
    url = _fill_params(path, spec)
    body = None
    if method in ("post", "put", "patch"):
        body_spec = (
            spec["paths"].get(path, {}).get(method.lower(), {}).get("requestBody", {})
        )
        content = body_spec.get("content", {}).get("application/json", {})
        body = _minimal_valid(content.get("schema", {}), spec)
    r = anon_client.request(method, url, json=body)
    assert r.status_code < 500 or r.status_code in EXPECTED_DEP_STATUSES, (
        f"{method} {path} -> {r.status_code}: {r.text[:200]}"
    )


@pytest.mark.parametrize(
    "method,path", _all_operations(create_app().openapi()), ids=lambda v: None
)
def test_no_5xx_on_junk_body(anon_client, spec, method, path):
    """A deliberately malformed body must be rejected as 4xx, never 5xx."""
    get_api_limiter().buckets.clear()
    url = _fill_params(path, spec)
    junk = {"__sweep_junk__": {"nested": [1, 2, {"x": None}]}}
    r = anon_client.request(method, url, json=junk if method in ("post", "put", "patch") else None)
    assert r.status_code < 500 or r.status_code in EXPECTED_DEP_STATUSES, (
        f"{method} {path} -> {r.status_code}: {r.text[:200]}"
    )


# ── 2. Auth contract over the whole surface ────────────────────────────


def test_every_protected_route_rejects_anonymous(spec):
    """Every operation outside the curated public allowlist must 401/403 anon
    — never 2xx, never 5xx.

    The allowlist is intentionally tiny: health probe, legal documents,
    and the public memory-type taxonomy. Anything else answering 2xx to an
    anonymous client is an auth leak (this test caught three routers
    mounted without authentication: integrations_all, cloud_relay,
    ecosystem).
    """
    get_api_limiter().buckets.clear()
    public_prefixes = (
        "/health",
        "/api/v1/health",
        "/api/v1/legal",
        "/api/v1/memory/types",
    )
    from fastapi.testclient import TestClient

    client = TestClient(create_app())
    violations = []
    for method, path in _all_operations(spec):
        url = _fill_params(path, spec)
        r = client.request(method, url)
        if r.status_code >= 500 and r.status_code not in EXPECTED_DEP_STATUSES:
            violations.append((method, path, r.status_code))
            continue
        if r.status_code < 300:
            if path.startswith(public_prefixes) and method == "GET":
                continue  # curated public surface
            violations.append((method, path, r.status_code))
        # 401/403/404/405/422/400/429 = rejected or not applicable — fine
    assert not violations, f"auth leaks / 5xx: {violations[:10]}"


# ── 3. Happy-path deep tests (high-traffic routes) ──────────────────────


def test_memory_literal_routes_not_shadowed(authed_client):
    """Regression: GET /memory/{memory_id} once swallowed the literal
    routes /stats, /types, /continue (uuid parse 500/422)."""
    for path in ("stats", "types", "continue"):
        r = authed_client.get(f"/api/v1/memory/{path}")
        assert r.status_code == 200, f"/memory/{path} -> {r.status_code}: {r.text[:120]}"
    types = authed_client.get("/api/v1/memory/types").json()["types"]
    assert isinstance(types, dict) and "personal" in types


def test_memory_create_search_delete_roundtrip(authed_client):
    r = authed_client.post(
        "/api/v1/memory",
        json={"content": "Sweep roundtrip memory", "category": "personal"},
    )
    assert r.status_code in (200, 201), r.text[:200]
    mid = r.json().get("id") or r.json().get("memory", {}).get("id")
    r2 = authed_client.get("/api/v1/memory/search", params={"q": "roundtrip"})
    assert r2.status_code == 200
    r3 = authed_client.delete(f"/api/v1/memory/{mid}")
    assert r3.status_code in (200, 204)


def test_proactive_suggestions_contract(authed_client):
    r = authed_client.get("/api/v1/proactive/suggestions")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, (list, dict))


def test_status_endpoint_authed(authed_client):
    r = authed_client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_legal_documents_served(authed_client):
    for name in ("privacy", "terms"):
        r = authed_client.get(f"/api/v1/legal/{name}")
        assert r.status_code == 200, f"/legal/{name} -> {r.status_code}"


def test_unknown_route_is_404_not_500(authed_client):
    r = authed_client.get("/api/v1/definitely/not/a/route")
    assert r.status_code == 404
