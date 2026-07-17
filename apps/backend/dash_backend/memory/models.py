"""Memory models for the Phase 3 persistent memory API.

This module re-exports the existing SQLAlchemy ORM model from
`dash_backend.db.models.memory` to keep changes minimal while satisfying
the required package structure.
"""

from __future__ import annotations

from dash_backend.db.models.memory import Memory

__all__ = ["Memory"]

