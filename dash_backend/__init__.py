"""Compatibility package for tests.

The real backend package lives under apps/backend/dash_backend.
This shim makes `import dash_backend` work when the repository root is
on PYTHONPATH (as in our pytest runs).
"""

from __future__ import annotations

import pkgutil
import pathlib

# Extend this package's namespace to include the actual implementation.
__path__ = pkgutil.extend_path(__path__, __name__)  # type: ignore[name-defined]

_here = pathlib.Path(__file__).resolve()
_repo_root = _here.parent.parent
_real_pkg = _repo_root / "apps" / "backend" / "dash_backend"

if _real_pkg.exists():
    __path__.append(str(_real_pkg))  # type: ignore[attr-defined]

# Re-export version for modules that do `from dash_backend import __version__`.
try:
    from dash_backend._version import __version__  # type: ignore
except Exception:
    __version__ = "0.1.0"


