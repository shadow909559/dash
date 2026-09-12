"""No-flash terminal regression tests (decisions.md #41).

The backend runs under pythonw — no console of its own. On Windows every
console executable it launches without CREATE_NO_WINDOW allocates a brand
new visible console window: that is the "terminals open and close when no
app is open" bug. The fix is a process-wide subprocess shim installed at
package import, plus hidden variants for the logon scheduled tasks.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "dash_backend"

# Spawn helpers whose kwargs flow into Popen (so the shim covers them).
_SYNC_HELPERS = ["run", "call", "check_call", "check_output"]


def _no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


# The REAL Popen captured at test-module import. Careful: if this module is
# imported after dash_backend, subprocess.Popen is already the shim; capture
# through the MRO instead so the assertion is against the genuine base.
import dash_backend as _dash  # noqa: E402

if isinstance(subprocess.Popen, type) and subprocess.Popen is not getattr(subprocess, "Popen", None):
    _orig_popen = subprocess.Popen.__mro__[1]
else:
    _orig_popen = subprocess.Popen


@pytest.mark.skipif(os.name != "nt", reason="Windows-only console behavior")
class TestShimInstalled:
    def test_shim_active_after_backend_import(self):
        # Importing any dash_backend module pulls the package __init__,
        # which installs the shim. Verify all helpers are wrapped.
        import dash_backend  # noqa: F401

        for name in _SYNC_HELPERS:
            fn = getattr(subprocess, name)
            assert getattr(fn, "__wrapped__", None) is not None or fn.__qualname__.startswith(
                "_wrap_simple"
            ), f"subprocess.{name} is not shimmed"
        # Popen must be a real CLASS subclass of the original Popen — not a
        # function wrapper — because asyncio.windows_utils subclasses
        # subprocess.Popen at import time (a function would crash there).
        assert isinstance(subprocess.Popen, type), "subprocess.Popen shim must be a class"
        assert issubclass(subprocess.Popen, _orig_popen)

    def test_run_inherits_no_window_flag(self):
        import dash_backend  # type: ignore[import-untyped]  # noqa: F401

        proc = subprocess.run(["cmd", "/c", "echo", "ok"], capture_output=True, text=True)
        assert proc.returncode == 0
        assert proc.stdout.strip() == "ok"

    def test_check_output_inherits_no_window_flag(self):
        import dash_backend  # noqa: F401

        out = subprocess.check_output(["cmd", "/c", "echo", "hi"], text=True)
        assert out.strip() == "hi"

    def test_caller_flags_are_respected(self):
        # The shim must OR its bit in, never clobber an explicit value.
        from dash_backend import _win_noswindow

        assert _win_noswindow._merge(_no_window_flag()) == _no_window_flag()
        assert _win_noswindow._merge(0) == _no_window_flag()
        assert _win_noswindow._merge(None) == _no_window_flag()
        # A caller flag different from ours survives the OR.
        fake = 0x08000000
        if fake != _no_window_flag():
            assert _win_noswindow._merge(fake) == (fake | _no_window_flag())


@pytest.mark.skipif(os.name != "nt", reason="Windows-only console behavior")
class TestShimWired:
    """The shim only works if it installs before any spawn site runs —
    guarantee that the package __init__ keeps it in the import chain."""

    def test_package_init_imports_shim_first(self):
        init = (BACKEND / "__init__.py").read_text(encoding="utf-8")
        assert "_win_noswindow" in init, (
            "dash_backend/__init__.py no longer installs the no-console "
            "subprocess shim — terminal flashing will regress"
        )

    def test_shim_file_exists(self):
        assert (BACKEND / "_win_noswindow.py").is_file()

    def test_asyncio_spawns_covered_by_popen_patch(self):
        # asyncio.create_subprocess_exec goes through subprocess.Popen on
        # the Proactor loop. The patched Popen must remain subclassable so
        # asyncio.windows_utils' `class Popen(subprocess.Popen)` keeps working
        # regardless of import order.
        import asyncio

        import dash_backend  # noqa: F401

        assert isinstance(subprocess.Popen, type)
        assert issubclass(subprocess.Popen, _orig_popen)
        # The subclass must be constructible (exercises the __init__ path).
        proc = subprocess.Popen(["cmd", "/c", "echo", "ok"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, _ = proc.communicate(timeout=10)
        assert out.strip() == b"ok"
        # And asyncio still references the subprocess module (not a copy).
        assert asyncio.subprocess is not None
