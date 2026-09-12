"""DASH FastAPI backend."""

__version__ = "0.1.0"

# Windows: force CREATE_NO_WINDOW on every console subprocess the backend
# spawns (decisions.md #41). Importing the shim first guarantees all later
# module-level and runtime spawn sites — subprocess.run/Popen and asyncio's
# create_subprocess_* — launch without allocating a visible console.
# No-op on non-Windows and in test environments that stub subprocess.
from dash_backend import _win_noswindow as _win_noswindow  # noqa: F401,E402  (import before submodules)
