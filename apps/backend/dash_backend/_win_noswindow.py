"""Force CREATE_NO_WINDOW on every console subprocess DASH spawns.

Problem this solves (decisions.md #41): the backend runs under pythonw —
it has NO console of its own. On Windows, any console executable it
launches without an explicit creation flag allocates a brand-new visible
console. That is why terminal windows flash open/closed while DASH idles
in the tray: system stats polling, git probes, wmic, tasklist, ping,
winget update checks, powershell one-liners — every one allocated a
console the user never asked for.

Patching the `subprocess` module at attribute level covers:
  - all `subprocess.run / Popen / call / check_output / check_call` sites
  - `asyncio.create_subprocess_exec/_shell` — the Windows Proactor
    transport spawns through `subprocess.Popen` internally, so those
    ~20 async call sites are covered by the same patch.

Call sites that pass their own creationflags are honored: the no-window
bit is only OR-ed in. Non-Windows platforms are untouched (the flag does
not exist there), making this a no-op during development on other OSes
and in every test run on Linux CI.
"""

from __future__ import annotations

import subprocess
import sys

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_applied = False


def _merge(creationflags: int | None) -> int:
    """OR the no-window bit into whatever the caller already asked for."""
    return (creationflags or 0) | _NO_WINDOW


class _NoWindowPopen(subprocess.Popen):
    """Real subclass, NOT a function wrapper: asyncio.windows_utils does
    ``class Popen(subprocess.Popen)`` at import time — subclassing the
    original function-wrapper crashed with ``TypeError: function()
    argument 'code' must be code, not str`` whenever asyncio's Windows
    modules were imported after dash_backend (import-order luck previously
    hid this). A class can be subclassed safely by anyone, anytime."""

    def __init__(self, *args, **kwargs):
        if _NO_WINDOW:
            kwargs["creationflags"] = _merge(kwargs.get("creationflags"))
        super().__init__(*args, **kwargs)


def _wrap_simple(orig):
    """Wrap run/call/check_call/check_output — same kwargs shape."""

    def simple(*args, **kwargs):
        if _NO_WINDOW:
            kwargs["creationflags"] = _merge(kwargs.get("creationflags"))
        return orig(*args, **kwargs)

    return simple


def install() -> None:
    """Patch subprocess once per process. Safe to call repeatedly."""
    global _applied
    if _applied or not _NO_WINDOW or sys.platform != "win32":
        return
    subprocess.Popen = _NoWindowPopen  # type: ignore[assignment]
    subprocess.run = _wrap_simple(subprocess.run)  # type: ignore[assignment]
    subprocess.call = _wrap_simple(subprocess.call)  # type: ignore[assignment]
    subprocess.check_call = _wrap_simple(subprocess.check_call)  # type: ignore[assignment]
    subprocess.check_output = _wrap_simple(subprocess.check_output)  # type: ignore[assignment]
    _applied = True


# Apply on import: dash_backend/__init__.py imports this module before any
# route/service submodule loads, so every later spawn site is covered.
install()
