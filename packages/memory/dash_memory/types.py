"""Memory record types (scaffold)."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """Minimal memory record structure."""

    id: str = Field(min_length=1)
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
