"""Agent base types (scaffold)."""

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Minimal agent configuration."""

    name: str = Field(min_length=1)
    description: str = ""
