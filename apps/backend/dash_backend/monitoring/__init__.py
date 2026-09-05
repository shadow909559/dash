"""DASH production monitoring & diagnostics.

Provides health aggregation, self-diagnostics, and automatic repair routines
for the DASH backend. Additive — does not replace existing performance or
security modules.
"""

from dash_backend.monitoring.diagnostics import (
    DiagnosticsService,
    get_diagnostics_service,
)
from dash_backend.monitoring.repair import (
    RepairRoutine,
    get_repair_routine,
)

__all__ = [
    "DiagnosticsService",
    "get_diagnostics_service",
    "RepairRoutine",
    "get_repair_routine",
]
