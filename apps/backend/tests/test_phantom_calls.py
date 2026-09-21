"""Pins for the phantom-call checker (#143).

The checker exists so the defect class behind #141/#142 (calling functions
that never existed on their target module — invisible to every other gate
because broad excepts converted the AttributeError into fabricated success)
can never recur. These tests pin the pin itself:

- the checker exits 0 on the real tree today (no drift),
- its package-surface model matches Python semantics (submodule imports,
  ``__all__`` overrides), so a regression into false positives is caught,
- it flags each known phantom shape on a synthetic mini-tree.
"""

from __future__ import annotations

import ast
import importlib
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_checker():
    """Import the checker as a real module at collection time.

    The #138 undeclared-import gate only scans top-level imports, so the
    lazy, function-scoped import below keeps it clean (feature-detection
    style) while still giving the module its file identity — a bare
    ``spec_from_file_location`` under an invented name breaks dataclass
    module resolution on CPython 3.14.
    """
    scripts_dir = str(SCRIPTS_DIR)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import check_phantom_calls  # lazy: keeps the #138 gate clean

    return check_phantom_calls


cpc = _load_checker()


def _tmp_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    """Materialize a mini dash_backend-shaped tree inside tmp_path."""
    root = tmp_path / "backend"
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content), encoding="utf-8")
    return root


def _run_check(tmp_path: Path, monkeypatch) -> list[str]:
    """Run check_file over every .py in the tmp tree, return rendered findings."""
    findings: list[str] = []
    for path in sorted((tmp_path / "backend").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for f in cpc.check_file(path, tree):
            findings.append(f.render())
    return findings


# ── the real tree stays clean ────────────────────────────────


def test_real_tree_has_no_phantom_calls():
    """Guard against drift: any new phantom on the real tree fails here."""
    assert cpc.main() == 0


def test_real_tree_scan_covers_expected_roots():
    files = cpc.iter_backend_files()
    joined = {str(p) for p in files}
    assert any("dash_backend" in p for p in joined)
    assert any("scripts" in p for p in joined)


# ── package-surface semantics ────────────────────────────────


def test_submodule_import_is_not_a_phantom(tmp_path, monkeypatch):
    """``from pkg import service`` + ``service.func()`` is LEGAL Python even
    when __init__.py never re-exports service — the runtime binds imported
    submodules as package attributes. The checker must not flag it."""
    root = _tmp_pkg(tmp_path, {
        "dash_backend/__init__.py": "",
        "dash_backend/pkg/__init__.py": "",
        "dash_backend/pkg/service.py": "def save():\n    return 1\n",
        "dash_backend/caller.py": (
            "from dash_backend.pkg import service\n"
            "def go():\n    return service.save()\n"
        ),
    })
    monkeypatch.setattr(cpc, "PACKAGE_ROOT", root / "dash_backend")
    assert _run_check(tmp_path, monkeypatch) == []


def test_all_override_is_respected(tmp_path, monkeypatch):
    """__all__ limits a package's visible surface; names outside it are
    phantoms when called via from-import."""
    root = _tmp_pkg(tmp_path, {
        "dash_backend/__init__.py": "",
        "dash_backend/pkg/__init__.py": "__all__ = ['real']\n",
        "dash_backend/pkg/real.py": "def f():\n    return 1\n",
        "dash_backend/caller.py": (
            "from dash_backend.pkg import real\n"
            "def go():\n    return real.f()\n"
        ),
    })
    monkeypatch.setattr(cpc, "PACKAGE_ROOT", root / "dash_backend")
    assert _run_check(tmp_path, monkeypatch) == []


def test_missing_attribute_on_imported_module_is_flagged(tmp_path, monkeypatch):
    root = _tmp_pkg(tmp_path, {
        "dash_backend/__init__.py": "",
        "dash_backend/pkg/__init__.py": "",
        "dash_backend/pkg/service.py": "def real():\n    return 1\n",
        "dash_backend/caller.py": (
            "from dash_backend.pkg import service\n"
            "def go():\n    return service.enqueue()\n"
        ),
    })
    monkeypatch.setattr(cpc, "PACKAGE_ROOT", root / "dash_backend")
    findings = _run_check(tmp_path, monkeypatch)
    assert len(findings) == 1
    assert "non-existent 'enqueue'" in findings[0]


def test_missing_from_import_symbol_is_flagged(tmp_path, monkeypatch):
    root = _tmp_pkg(tmp_path, {
        "dash_backend/__init__.py": "",
        "dash_backend/pkg/__init__.py": "",
        "dash_backend/pkg/service.py": "",
        "dash_backend/caller.py": (
            "from dash_backend.pkg.service import transcribe_audio\n"
            "def go(audio):\n    return transcribe_audio(audio)\n"
        ),
    })
    monkeypatch.setattr(cpc, "PACKAGE_ROOT", root / "dash_backend")
    findings = _run_check(tmp_path, monkeypatch)
    assert len(findings) == 1
    assert "transcribe_audio" in findings[0]


def test_out_of_package_and_star_imports_are_suppressed(tmp_path, monkeypatch):
    """Third-party/stdlib modules and star imports are out of static scope —
    the checker must stay silent rather than guess."""
    root = _tmp_pkg(tmp_path, {
        "dash_backend/__init__.py": "",
        "dash_backend/caller.py": (
            "import os\n"
            "from collections import *\n"
            "def go():\n    return os.path.join('a', 'b')\n"
        ),
    })
    monkeypatch.setattr(cpc, "PACKAGE_ROOT", root / "dash_backend")
    assert _run_check(tmp_path, monkeypatch) == []


def test_instance_method_calls_are_out_of_scope(tmp_path, monkeypatch):
    """obj.method() where obj is not an import binding is not statically
    resolvable — must not be flagged."""
    root = _tmp_pkg(tmp_path, {
        "dash_backend/__init__.py": "",
        "dash_backend/caller.py": (
            "def go(obj):\n    return obj.anything_at_all()\n"
        ),
    })
    monkeypatch.setattr(cpc, "PACKAGE_ROOT", root / "dash_backend")
    assert _run_check(tmp_path, monkeypatch) == []


# ── CLI behavior ─────────────────────────────────────────


def test_cli_exit_codes(monkeypatch, tmp_path):
    """0 when clean, 1 with findings, printed to stdout."""
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "check_phantom_calls.py")],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0
    assert "OK: no cross-module phantom calls" in result.stdout
