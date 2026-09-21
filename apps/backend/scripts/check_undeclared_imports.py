"""Fail when backend production code imports a third-party module that is
declared nowhere in pyproject/requirements — the numpy-class CI failure (#137).

numpy arrived transitively on dev machines and CI collection died with
``ModuleNotFoundError``. This checker makes that class of bug a fast,
deterministic, no-network failure at lint time instead.

Policy (measured against the real codebase, not guessed):

- **Unguarded top-level** import in ``dash_backend/`` -> FAILURE. Module-scope
  code runs for *every* importer at *collection* time, so an undeclared
  module there breaks CI exactly like numpy did. This is the only failing
  class — guarded and lazy imports are feature-detection by design and are
  reported as warnings only.
- Declared = pyproject [project.dependencies] + every optional extra
  (dev/vision/voice/...), mapped through a distribution->import-name table
  and cross-checked against the local environment's ``packages_distributions``
  when available (wheels whose import name differs from the dist name).
- **Allowlist** exists only for modules that are genuinely undeclared yet
  always importable on supported platforms (stdlib in disguise); every entry
  requires a reason and every allowlisted module is still *reported* so the
  list cannot grow silently.

Usage:
    python scripts/check_undeclared_imports.py            # exit 1 on violation
    python --check ...                                    # same via CI step
Scans dash_backend/, tests/ and scripts/ so test-only and script-only
imports (like dev-extra cv2) are judged under the same policy.
"""
from __future__ import annotations

import ast
import os
import re
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = ("dash_backend", "tests", "scripts")

# distribution name -> import name(s), for names AST cannot guess.
DIST_TO_IMPORT = {
    "pillow": "PIL",
    "python-multipart": "multipart",
    "python-dotenv": "dotenv",
    "py-cpuinfo": "cpuinfo",
    "opencv-python-headless": "cv2",
    "faster-whisper": "faster_whisper",
    "openai-whisper": "whisper",
    "speechrecognition": "speech_recognition",
    "beautifulsoup4": "bs4",
    "pywin32": {"win32api", "win32con", "win32gui", "win32process", "pythonwin"},
    "pyobjc": "objc",
    "protobuf": "google",
    "google-generativeai": "google",
    "grpcio": "google",
}

# Top-level names that are the project's own code, never third-party.
OWN_PACKAGES = {"dash_backend", "tests"}

# Modules that may be imported without a declaration. Each entry needs a
# reason; CI prints the full list on every run so it cannot grow silently.
ALLOWLIST = {
    # packaging/dist-info shim: importable wherever pip itself works.
    "pkg_resources": "setuptools shim, importable wherever pip works",
}


def _collect_declared_import_names() -> set[str]:
    data = tomllib.loads((BACKEND_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared: set[str] = set()
    for req in data["project"]["dependencies"] + sum(
        data["project"].get("optional-dependencies", {}).values(), []
    ):
        name = re.split(r"[;\[><=!~\s]", req.strip(), maxsplit=1)[0].strip().lower()
        if name:
            declared.add(name)

    imports: set[str] = set(OWN_PACKAGES)
    for dist in declared:
        mapped = DIST_TO_IMPORT.get(dist)
        if mapped is None:
            imports.add(dist.replace("-", "_"))
            continue
        if isinstance(mapped, str):
            imports.add(mapped)
        else:
            imports.update(mapped)

    # Environment cross-check: a declared distribution may expose several
    # import names (e.g. `cryptography` x y.z); trust the local metadata
    # when it agrees with pyproject.
    try:
        pd = packages_distributions()
    except Exception:
        pd = {}
    for imp, dists in pd.items():
        if any(d.lower().replace("_", "-") in declared for d in dists):
            imports.add(imp)
    return imports


def _classify(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    """lazy (function-scoped) / guarded (ImportError etc.) / top-level."""
    chain = []
    cur = node
    while cur in parents:
        cur = parents[cur]
        chain.append(cur)
    for p in chain:
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return "lazy"
        if isinstance(p, ast.Try):
            for h in p.handlers:
                if h.type is None:
                    return "guarded"
                if isinstance(h.type, ast.Tuple):
                    names = [e.id for e in h.type.elts if isinstance(e, ast.Name)]
                elif isinstance(h.type, ast.Name):
                    names = [h.type.id]
                else:
                    names = []
                if any(n in ("ImportError", "ModuleNotFoundError") for n in names):
                    return "guarded"
        if isinstance(p, ast.If):
            src = ast.unparse(p.test)
            if any(
                k in src
                for k in ("importlib", "find_spec", "version_info", "sys.platform", "os.name")
            ):
                return "guarded"
    return "top-level"


def _iter_imports(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node, node.module.split(".")[0]


def check() -> tuple[list[str], list[str]]:
    declared_imports = _collect_declared_import_names()
    stdlib = set(sys.stdlib_module_names)

    errors: list[str] = []
    info: list[str] = []

    for base in SCAN_DIRS:
        for dirpath, dirnames, filenames in os.walk(BACKEND_ROOT / base):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".pytest_cache")]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                path = Path(dirpath) / fn
                rel = path.relative_to(BACKEND_ROOT).as_posix()
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
                except SyntaxError:
                    continue
                parents: dict[ast.AST, ast.AST] = {}
                for p in ast.walk(tree):
                    for c in ast.iter_child_nodes(p):
                        parents[c] = p
                for node, top in _iter_imports(tree):
                    if top in stdlib or top in declared_imports or top in ALLOWLIST:
                        if top in ALLOWLIST:
                            info.append(f"allowlisted import '{top}' at {rel}:{node.lineno}")
                        continue
                    kind = _classify(node, parents)
                    site = f"{rel}:{node.lineno}"
                    if kind == "top-level":
                        errors.append(
                            f"UNDECLARED top-level import '{top}' at {site} - "
                            f"declare it in pyproject/requirements or guard it "
                            f"(try/except ImportError) and import lazily"
                        )
                    else:
                        info.append(f"optional '{top}' ({kind}) at {site}")

    return errors, info


def main() -> int:
    errors, info = check()
    for line in info:
        print(f"note: {line}")
    if errors:
        print("\n=== FAILURES (undeclared top-level imports) ===", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        print(
            f"\n{len(errors)} undeclared top-level import(s). "
            "Fix: declare the dependency or guard the import.",
            file=sys.stderr,
        )
        return 1
    print("OK: no undeclared top-level third-party imports.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
