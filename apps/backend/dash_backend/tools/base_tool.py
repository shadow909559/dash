"""Base tool interface that all Dash tools must implement.

Defines the contract for tool name, description, parameters,
permission levels, execution, and registration.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class PermissionLevel(enum.Enum):
    """Granular permission levels for tool execution.

    Values are string labels for readability, but comparison operators are
    implemented based on internal numeric ranks to preserve ordering semantics.
    """

    AUTO = "auto"       # Execute without confirmation
    CONFIRM = "confirm"    # Require user confirmation
    RESTRICTED = "restricted" # Always blocked unless explicitly approved

    # NOTE: do NOT store the rank table as a class attribute. On Python 3.14
    # the enum machinery converts plain dict class attributes into members,
    # which breaks ordering comparisons for EVERY tool.
    def _rank(self) -> int:
        return {"auto": 0, "confirm": 1, "restricted": 2}[self.value]

    # Implement ordering based on rank
    def __ge__(self, other):
        if not isinstance(other, PermissionLevel):
            return NotImplemented
        return self._rank() >= other._rank()

    def __gt__(self, other):
        if not isinstance(other, PermissionLevel):
            return NotImplemented
        return self._rank() > other._rank()

    def __le__(self, other):
        if not isinstance(other, PermissionLevel):
            return NotImplemented
        return self._rank() <= other._rank()

    def __lt__(self, other):
        if not isinstance(other, PermissionLevel):
            return NotImplemented
        return self._rank() < other._rank()

@dataclass
class ToolParameter:
    """Describes a single parameter accepted by a tool."""

    name: str
    description: str
    type: str = "string"  # JSON Schema type
    required: bool = True
    default: Any | None = None
    enum: list[str] | None = None


@dataclass
class ToolSpec:
    """Full specification of a tool for LLM function calling.

    This is serialized into the JSON payload sent to the LLM
    as a `tool` definition (OpenAI-compatible).
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    permission_level: PermissionLevel = PermissionLevel.AUTO
    requires_confirmation: bool = False
    category: str = "general"

    def to_openai_tool(self) -> dict[str, Any]:
        """Return OpenAI-compatible tool definition."""
        properties: dict[str, Any] = {}
        required_params: list[str] = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.default is not None:
                prop["default"] = param.default
            properties[param.name] = prop
            if param.required:
                required_params.append(param.name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }
        if required_params:
            schema["required"] = required_params

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


@dataclass
class ToolContext:
    """Context provided to a tool during execution.

    Carries request metadata, user identity, and services the tool
    may need (e.g., database sessions).
    """

    user_id: str | None = None
    conversation_id: str | None = None
    request_id: str | None = None
    working_directory: str = "."
    extra: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base class for all Dash tools.

    Every tool must provide:
        - name       : Unique identifier (snake_case)
        - description: Human-readable description
        - parameters : List of ToolParameter
        - permission : PermissionLevel
        - category   : Grouping label

    Subclasses must implement:
        - execute(context, **kwargs) -> ToolResult
    """

    name: str = ""
    description: str = ""
    parameters: list[ToolParameter] = []
    permission_level: PermissionLevel = PermissionLevel.AUTO
    category: str = "general"

    @property
    def requires_confirmation(self) -> bool:
        """Whether this tool always requires user confirmation."""
        return self.permission_level >= PermissionLevel.CONFIRM

    @property
    def spec(self) -> ToolSpec:
        """Return the full ToolSpec for this tool."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            permission_level=self.permission_level,
            requires_confirmation=self.requires_confirmation,
            category=self.category,
        )

    @abstractmethod
    async def execute(
        self,
        context: ToolContext,
        **kwargs: Any,
    ) -> "ToolResult":
        """Execute the tool with the given parameters and context.

        Args:
            context: Execution context (user, session, etc.)
            **kwargs: Tool-specific parameters matching `parameters`.

        Returns:
            ToolResult with status, output data, or error message.
        """
        ...

    def validate_args(self, **kwargs: Any) -> list[str]:
        """Validate arguments against declared parameters.

        Returns a list of error messages (empty if valid).
        """
        errors: list[str] = []
        param_map = {p.name: p for p in self.parameters}

        for param in self.parameters:
            if param.required and param.name not in kwargs:
                errors.append(f"Missing required parameter: '{param.name}'")
            if param.name in kwargs and param.enum:
                if kwargs[param.name] not in param.enum:
                    errors.append(
                        f"'{param.name}' must be one of {param.enum}, "
                        f"got '{kwargs[param.name]}'"
                    )

        # Warn about unknown parameters (not an error, just ignore)
        return errors