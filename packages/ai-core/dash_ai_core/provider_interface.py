"""Provider contract (no LLM calls).

A provider exposes model capabilities. This package contains only contracts
and type definitions, not concrete provider implementations.
"""

from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    """Provider contract."""

    @property
    def name(self) -> str:
        """Human-readable provider name."""

    def is_available(self) -> bool:
        """Return whether the provider can be used in the current environment."""

    def supports(self, ability: str) -> bool:
        """Return whether this provider supports a given ability."""


