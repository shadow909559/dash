"""Prompt template types (scaffold)."""

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """Minimal prompt template structure."""

    name: str = Field(min_length=1)
    template: str = Field(min_length=1)
