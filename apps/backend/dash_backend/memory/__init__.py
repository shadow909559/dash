"""Persistent memory package.

Phase 3 expects this package layout.

This package contains thin wrappers/re-exports around the existing,
implemented memory model/service/routes to keep changes minimal.
"""

from dash_backend.memory.models import Memory
from dash_backend.memory.schemas import MemoryCreate, MemoryRead, MemoryUpdate

__all__ = [
    "Memory",
    "MemoryCreate",
    "MemoryRead",
    "MemoryUpdate",
]

