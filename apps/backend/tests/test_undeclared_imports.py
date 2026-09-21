"""Pin the undeclared-import checker (#138).

The checker exists so the numpy-class CI failure (#137 - a module imported
at top level but declared nowhere, invisible on dev machines where it
arrives transitively) can never recur: it fails on unguarded top-level
third-party imports and treats lazy/ImportError-guarded imports as the
feature-detection they are.

These tests pin the pin itself:
- the checker exits 0 on the real tree today (no drift since the fix), and
- it ACTUALLY FAILS on a planted violation (a vacuously-green checker is
  worth nothing), including when the violating module cannot be resolved
  from local metadata.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CHECKER = BACKEND_ROOT / "scripts" / "check_undeclared_imports.py"


def _run_checker() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_checker_passes_on_current_tree() -> None:
    """The real tree must be clean right now - guards the fix against drift."""
    proc = _run_checker()
    assert proc.returncode == 0, (
        f"undeclared-import checker failed on the current tree:\n{proc.stderr[-2000:]}"
    )
    assert "OK: no undeclared top-level third-party imports." in proc.stdout


def test_checker_fails_on_planted_violation(tmp_path: Path) -> None:
    """Anti-vacuous guard: a planted unguarded top-level import must fail.

    The planted module is also absent from the local environment, which
    proves the checker does not lean on what happens to be installed here.
    """
    probe = BACKEND_ROOT / "dash_backend" / "_ci_probe_undeclared_tmp.py"
    probe.write_text("import definitely_not_declared_xyz_module\n", encoding="utf-8")
    try:
        proc = _run_checker()
        assert proc.returncode == 1, "checker passed despite a planted violation"
        assert "definitely_not_declared_xyz_module" in proc.stderr
        assert "UNDECLARED top-level import" in proc.stderr
    finally:
        probe.unlink(missing_ok=True)
    # cleanup verified: the tree is clean again
    assert _run_checker().returncode == 0
