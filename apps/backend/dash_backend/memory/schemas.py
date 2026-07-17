"""Pydantic schemas for the Phase 3 persistent memory API.

This module re-exports the existing schemas from `dash_backend.api.schemas.memory`
so the new memory package structure required by Phase 3 is present without
changing API payloads.
"""

from __future__ import annotations

from dash_backend.api.schemas.memory import (  # noqa: F401
    MemoryCreate,
    MemoryListResponse,
    MemoryRead,
    MemorySearchResponse,
    MemoryUpdate,
)

# Phase 3 only requires Create/Read/Update. Re-export them explicitly.
__all__ = [
    "MemoryCreate",
    "MemoryRead",
    "MemoryUpdate",
]

