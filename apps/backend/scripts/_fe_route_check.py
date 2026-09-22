"""Frontend↔backend route parity check (#144).

Extracts every API call target from the desktop app source and matches it
against the backend's real route table (live OpenAPI when available, a
fresh snapshot otherwise, or a routes set injected by tests). Dynamic
template literals keep a ${...} marker so they can be matched against
FastAPI's {param} route syntax.

Importable (see tests/test_fe_route_parity.py) and runnable as a script:

    python scripts/_fe_route_check.py
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FE = ROOT / "apps" / "desktop" / "src"

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


# ── 1. Backend route table ────────────────────────────────────────────


def routes_from_openapi(spec: dict) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for path, methods in (spec.get("paths") or {}).items():
        for method in methods:
            if method.upper() in HTTP_METHODS:
                out.add((method.upper(), path))
    return out


def openapi_routes() -> set[tuple[str, str]]:
    """Prefer a fresh snapshot file; fall back to any live bench server."""
    try:
        snap = Path(__file__).resolve().parents[2] / "tmp" / "openapi_dash.json"
        if snap.exists() and (time.time() - snap.stat().st_mtime) < 3600:
            with open(snap, encoding="utf-8") as fh:
                return routes_from_openapi(json.load(fh))
        with urllib.request.urlopen(
            "http://127.0.0.1:8033/openapi.json", timeout=3
        ) as resp:
            return routes_from_openapi(json.load(resp))
    except Exception:
        return set()


# ── 2. Frontend call targets ──────────────────────────────────────────


def extract_fe_targets(fe_dir: Path) -> set[str]:
    targets: set[str] = set()
    tmpl = re.compile(r"`([^`]*)`")
    for f in list(fe_dir.rglob("*.ts")) + list(fe_dir.rglob("*.tsx")):
        src = f.read_text(encoding="utf-8", errors="replace")
        # drop comments (doc comments name routes too); keep http(s):// URLs
        src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        src = re.sub(r"(?<!:)//[^\n]*", "", src)
        # every backtick literal that contains a '/' and looks like a call target
        for m in tmpl.finditer(src):
            lit = m.group(1)
            if "/" not in lit or lit.strip().startswith("//"):
                continue
            # external provider bases (user-configured OpenAI-compatible
            # URLs) are not backend routes
            if lit.startswith("${baseUrl}"):
                continue
            head = src[max(0, m.start() - 120) : m.start()]
            if re.search(
                r"(authFetch|apiFetch|request|fetch|\.get|\.post|\.put|\.patch|\.del|\.delete)\s*[<(]?\s*$",
                head,
            ):
                targets.add(lit.strip())
        # plain string args — only when the call's first argument IS the
        # string (a nested literal inside a template's ${...} is not a
        # call target). Bare fetch() is included on purpose: it was the
        # broken pattern this gate was built for (no auth header).
        for m in re.finditer(
            r"(?:authFetch|apiFetch|request|fetch)\s*\(\s*[\"'](/[^\"']+)[\"']", src
        ):
            targets.add(m.group(1))
    return targets


# ── 3. Normalization + matching ───────────────────────────────────────


def normalize_fe(t: str) -> str:
    # The frontend's ${API}/${API_BASE} expands to 'http://host:8000/api/v1'
    # (VITE_API_URL default), so strip it AND its /api/v1 suffix; relative
    # authFetch('/x') paths resolve against the same /api/v1 base.
    t2 = t
    # ${RAG} expands to '<host>/api/v1/rag' — keep the /rag segment
    if t2.startswith("${RAG}"):
        t2 = "/rag" + t2[len("${RAG}") :]
    for prefix in ("${API}", "${API_BASE}", "${API_ORIGIN}", "${base}", "${BASE}", "${RAG}"):
        if t2.startswith(prefix):
            t2 = t2[len(prefix) :]
            break
    else:
        t2 = re.sub(r"^\$\{[^}]*\}", "", t2)
    t2 = re.sub(r"^/api/v1(?=/)", "", t2)
    t2 = re.sub(r"\$\{[^}]*\}", "*", t2)
    if not t2.startswith("/"):
        t2 = "/" + t2
    return t2.split("?")[0]


def normalize_be(p: str) -> str:
    p = p.split("?")[0]
    # live OpenAPI paths carry the full /api/v1 prefix; strip for comparison
    return re.sub(r"^/api/v1(?=/)", "", p)


def missing_targets(
    fe_dir: Path, routes: set[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Return [(normalized-target, source-literal)] with no matching route."""
    be_set = {normalize_be(p) for _, p in routes}

    def matches(fe_norm: str) -> bool:
        if fe_norm in be_set:
            return True
        # trailing-wildcard form: "/assistant*" matches any "/assistant/..."
        # (only for prefix-style wildcards — a path with an inner '*' like
        # /agent/task/*/* must fall through to segment matching)
        if fe_norm.endswith("*") and "*" not in fe_norm[:-1]:
            base = fe_norm[:-1].rstrip("/")
            return any(be.startswith(base + "/") or be == base for be in be_set)
        fe_parts = fe_norm.strip("/").split("/")
        for be in be_set:
            be_parts = be.strip("/").split("/")
            if len(fe_parts) != len(be_parts):
                continue
            if all(
                bp.startswith("{") or fp == bp or bp == "*" or fp == "*"
                for fp, bp in zip(fe_parts, be_parts)
            ):
                return True
        return False

    fe_set = {normalize_fe(t): t for t in extract_fe_targets(fe_dir)}
    return sorted((fe, src) for fe, src in fe_set.items() if not matches(fe))


def main() -> int:
    routes = openapi_routes()
    source = "live OpenAPI/snapshot" if routes else "none"
    print(f"backend routes: {len(routes)} ({source})")
    if not routes:
        print("no route table available — cannot verify", file=sys.stderr)
        return 2
    targets = extract_fe_targets(FE)
    print(f"frontend call targets: {len(targets)}")
    missing = missing_targets(FE, routes)
    if missing:
        print(f"\n=== frontend targets with NO matching backend route ({len(missing)}) ===")
        for fe, src in missing:
            print(f"  {fe}    [from: {src[:70]}]")
        return 1
    print("all frontend call targets match a backend route")
    return 0


if __name__ == "__main__":
    sys.exit(main())
