"""Pydantic schemas for agents API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(..., max_length=128)
    description: str | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None


class AgentRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str | None
    allowed_tools: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    allowed_tools: list[str] | None = None
