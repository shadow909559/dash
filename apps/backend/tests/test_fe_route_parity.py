"""Frontend↔backend route parity gate (#144).

The checker (scripts/_fe_route_check.py) extracts every API call target
from the desktop app source and matches it against the backend's real
route table. This test pins the pin itself — with routes derived from the
real FastAPI app via ``app.openapi()`` so CI needs no running server.

Pins:
- every frontend call target resolves to a real backend route (drift in
  either direction fails here, before it fails a user clicking a button),
- the matcher's semantics: FE ``*`` matches BE literal segments, FE
  prefix wildcards (``/assistant*``) match subtrees, ``${param}`` maps to
  BE ``{param}``, and query strings are ignored,
- extraction hygiene: comment-mentioned routes and external
  ``${baseUrl}`` calls are not call targets.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = BACKEND_ROOT / "scripts"

# Import the checker as a module without a package import (keeps the
# #138 undeclared-import gate clean — ``scripts`` is not a declared pkg).
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
_fec = importlib.import_module("_fe_route_check")

FE = Path(__file__).resolve().parents[2] / "desktop" / "src"


def _app_routes() -> set[tuple[str, str]]:
    from dash_backend.main import app

    return _fec.routes_from_openapi(app.openapi())


def test_every_frontend_call_target_has_a_backend_route():
    missing = _fec.missing_targets(FE, _app_routes())
    assert missing == [], (
        "frontend calls backend routes that do not exist — wire the call to "
        f"the real route or add the missing route: {missing}"
    )


def test_matcher_fe_wildcard_matches_be_literal_segment():
    routes = {("POST", "/api/v1/phase4/clipboard/{clip_id}/pin")}
    # FE dispatches /phase4/clipboard/${id}/pin; BE route is parametrized
    missing = _fec.missing_targets(FE.with_name("no-such-dir"), routes)
    assert missing == []


def _synth_fe(tmp_path: Path, body: str) -> Path:
    fe = tmp_path / "src"
    fe.mkdir(parents=True, exist_ok=True)
    (fe / "call.ts").write_text(body, encoding="utf-8")
    return fe


def test_synthetic_phantom_is_caught(tmp_path):
    fe = _synth_fe(tmp_path, "const x = fetch('/api/v1/definitely/not/a/route');\n")
    missing = _fec.missing_targets(fe, {("GET", "/api/v1/other")})
    assert [m[0] for m in missing] == ["/definitely/not/a/route"]


def test_synthetic_real_route_matches(tmp_path):
    fe = _synth_fe(
        tmp_path,
        "const x = fetch(`/api/v1/items/${id}/sub`);\n"
        "const y = authFetch('/api/v1/simple');\n",
    )
    routes = {
        ("GET", "/api/v1/items/{item_id}/sub"),
        ("GET", "/api/v1/simple"),
    }
    assert _fec.missing_targets(fe, routes) == []


def test_query_strings_are_ignored(tmp_path):
    fe = _synth_fe(tmp_path, "fetch(`/api/v1/files/browse?path=${encodeURIComponent(p)}`);\n")
    routes = {("GET", "/api/v1/files/browse")}
    assert _fec.missing_targets(fe, routes) == []


def test_fe_star_matches_be_literal(tmp_path):
    fe = _synth_fe(tmp_path, "fetch(`${API}/agent/task/${id}/${action}`);\n")
    routes = {("POST", "/api/v1/agent/task/{task_id}/cancel")}
    assert _fec.missing_targets(fe, routes) == []


def test_prefix_wildcard_matches_subtree(tmp_path):
    fe = _synth_fe(tmp_path, "fetch(`${API}/assistant${path}`);\n")
    routes = {("GET", "/api/v1/assistant/meetings")}
    assert _fec.missing_targets(fe, routes) == []


def test_external_base_urls_are_not_targets(tmp_path):
    fe = _synth_fe(
        tmp_path,
        "fetch(`${baseUrl}/chat/completions`, { method: 'POST' });\n",
    )
    assert _fec.missing_targets(fe, {("GET", "/api/v1/anything")}) == []


def test_comments_are_not_call_targets(tmp_path):
    fe = _synth_fe(
        tmp_path,
        "// See POST /api/v1/not/a/route for details\nexport const x = 1;\n",
    )
    assert _fec.missing_targets(fe, {("GET", "/api/v1/real")}) == []
