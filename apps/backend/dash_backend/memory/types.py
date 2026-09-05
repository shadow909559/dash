from __future__ import annotations

from enum import Enum


class MemoryType(str, Enum):
    Conversation = "Conversation"
    Fact = "Fact"
    Preference = "Preference"
    Task = "Task"
    Project = "Project"
    Person = "Person"
    Goal = "Goal"
    Summary = "Summary"


ALLOWED_MEMORY_TYPES: set[str] = {t.value for t in MemoryType}

