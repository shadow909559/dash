"""Agent ORM models."""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from dash_backend.db.base import Base
from dash_backend.db.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class Agent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents a configurable assistant persona."""

    __tablename__ = "agents"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_tools: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Agent id={self.id} name={self.name}>" 
