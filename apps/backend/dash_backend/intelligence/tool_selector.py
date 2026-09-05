"""Tool Selection - Tool matching and execution monitoring.

Implements intelligent tool selection:
- Tool matching based on task requirements
- Tool parameter extraction and validation
- Tool execution monitoring
- Tool result evaluation

Features:
- Semantic tool matching
- Parameter schema validation
- Execution timeout handling
- Result quality assessment
- Tool usage analytics
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ToolStatus(str, Enum):
    """Status of a tool."""
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    DEPRECATED = "deprecated"


class ExecutionStatus(str, Enum):
    """Status of tool execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""
    name: str
    type: str
    required: bool = True
    default: Any = None
    description: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "default": self.default,
            "description": self.description,
            "constraints": self.constraints,
        }


@dataclass
class Tool:
    """Represents an executable tool."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: ToolStatus = ToolStatus.AVAILABLE
    parameters: List[ToolParameter] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    handler: Optional[Callable] = None
    timeout: float = 30.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_count: int = 0
    success_count: int = 0
    last_executed: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "parameters": [p.to_dict() for p in self.parameters],
            "tags": self.tags,
            "category": self.category,
            "timeout": self.timeout,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
        }


@dataclass
class ToolExecution:
    """A tool execution record."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_id: str = ""
    tool_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


@dataclass
class ToolMatch:
    """Result of tool matching."""
    tool: Tool
    score: float
    reason: str = ""
    missing_parameters: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool.to_dict(),
            "score": self.score,
            "reason": self.reason,
            "missing_parameters": self.missing_parameters,
        }


class ToolSelector:
    """Tool matching, selection, and execution monitoring.

    Manages tool registry, matches tools to tasks, validates
    parameters, and monitors tool execution.
    """

    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._tool_index: Dict[str, List[str]] = {}  # tag -> tool_ids
        self._category_index: Dict[str, List[str]] = {}  # category -> tool_ids
        self._executions: List[ToolExecution] = []
        self._default_timeout = 30.0
        self._llm_matcher: Optional[Callable] = None

    def set_llm_matcher(self, matcher: Callable) -> None:
        """Set the LLM-based tool matcher."""
        self._llm_matcher = matcher

    def register_tool(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        parameters: Optional[List[ToolParameter]] = None,
        tags: Optional[List[str]] = None,
        category: str = "general",
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tool:
        """Register a new tool.

        Args:
            name: Tool name
            handler: Callable that implements the tool
            description: Tool description
            parameters: List of parameter definitions
            tags: Tags for discovery
            category: Tool category
            timeout: Execution timeout in seconds
            metadata: Additional metadata

        Returns:
            The registered tool
        """
        tool = Tool(
            name=name,
            description=description,
            parameters=parameters or [],
            tags=tags or [],
            category=category,
            handler=handler,
            timeout=timeout or self._default_timeout,
            metadata=metadata or {},
        )

        self._tools[tool.id] = tool

        # Update indexes
        for tag in tool.tags:
            if tag not in self._tool_index:
                self._tool_index[tag] = []
            self._tool_index[tag].append(tool.id)

        if tool.category not in self._category_index:
            self._category_index[tool.category] = []
        self._category_index[tool.category].append(tool.id)

        logger.info("Registered tool: %s", name)
        return tool

    def unregister_tool(self, tool_id: str) -> bool:
        """Unregister a tool."""
        tool = self._tools.get(tool_id)
        if not tool:
            return False

        # Remove from indexes
        for tag in tool.tags:
            if tag in self._tool_index:
                self._tool_index[tag] = [tid for tid in self._tool_index[tag] if tid != tool_id]

        if tool.category in self._category_index:
            self._category_index[tool.category] = [
                cid for cid in self._category_index[tool.category] if cid != tool_id
            ]

        del self._tools[tool_id]

        logger.info("Unregistered tool: %s", tool.name)
        return True

    def get_tool(self, tool_id: str) -> Optional[Tool]:
        """Get a tool by ID."""
        return self._tools.get(tool_id)

    def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        for tool in self._tools.values():
            if tool.name == name:
                return tool
        return None

    async def match_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> List[ToolMatch]:
        """Match tools to a task.

        Args:
            task: Task description
            context: Optional context for matching
            top_k: Number of top matches to return
            min_score: Minimum score threshold

        Returns:
            List of tool matches ranked by score
        """
        context = context or {}
        available_tools = [t for t in self._tools.values() if t.status == ToolStatus.AVAILABLE]

        if not available_tools:
            return []

        # If LLM matcher is available, use it
        if self._llm_matcher:
            try:
                return await self._llm_match(task, available_tools, context, top_k)
            except Exception as exc:
                logger.warning("LLM tool matching failed: %s", exc)

        # Fallback to keyword matching
        return self._keyword_match(task, available_tools, top_k, min_score)

    async def _llm_match(
        self,
        task: str,
        tools: List[Tool],
        context: Dict[str, Any],
        top_k: int,
    ) -> List[ToolMatch]:
        """Use LLM to match tools."""
        # Build tool descriptions
        tool_descriptions = "\n".join(
            f"- {tool.name}: {tool.description}"
            for tool in tools
        )

        prompt = (
            f"Given the task: {task}\n\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            "Select the most appropriate tools. Respond with JSON:\n"
            '[{"tool_name": "...", "score": 0.0-1.0, "reason": "..."}]'
        )

        try:
            response = await self._llm_matcher(prompt)
            import json
            matches_data = json.loads(response)

            matches = []
            for match_data in matches_data[:top_k]:
                tool = self.get_tool_by_name(match_data.get("tool_name", ""))
                if tool:
                    matches.append(
                        ToolMatch(
                            tool=tool,
                            score=match_data.get("score", 0.5),
                            reason=match_data.get("reason", ""),
                        )
                    )

            return matches
        except Exception as exc:
            logger.warning("LLM match parsing failed: %s", exc)
            return []

    def _keyword_match(
        self,
        task: str,
        tools: List[Tool],
        top_k: int,
        min_score: float,
    ) -> List[ToolMatch]:
        """Fallback keyword-based matching."""
        task_lower = task.lower()
        task_words = set(task_lower.split())

        scored = []
        for tool in tools:
            score = 0.0
            reason = ""

            # Check name match
            if tool.name.lower() in task_lower:
                score += 0.5
                reason += f"Name match; "

            # Check description match
            desc_lower = tool.description.lower()
            desc_words = set(desc_lower.split())
            overlap = len(task_words & desc_words)
            if overlap > 0:
                score += 0.3 * (overlap / len(task_words))
                reason += f"Description overlap ({overlap} words); "

            # Check tag match
            for tag in tool.tags:
                if tag.lower() in task_lower:
                    score += 0.2
                    reason += f"Tag match ({tag}); "

            if score >= min_score:
                scored.append(ToolMatch(tool=tool, score=score, reason=reason))

        # Sort by score
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[:top_k]

    async def extract_parameters(
        self,
        tool: Tool,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract parameters for a tool from a task.

        Args:
            tool: The tool to extract parameters for
            task: Task description
            context: Optional context

        Returns:
            Extracted parameters
        """
        context = context or {}
        parameters = {}

        # Try to extract from context first
        for param in tool.parameters:
            if param.name in context:
                parameters[param.name] = context[param.name]

        # Check for missing required parameters
        missing = [
            p.name for p in tool.parameters
            if p.required and p.name not in parameters
        ]

        if missing and self._llm_matcher:
            # Use LLM to extract missing parameters
            try:
                extracted = await self._llm_extract_parameters(tool, task, missing, context)
                parameters.update(extracted)
            except Exception as exc:
                logger.warning("LLM parameter extraction failed: %s", exc)

        return parameters

    async def _llm_extract_parameters(
        self,
        tool: Tool,
        task: str,
        missing_params: List[str],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Use LLM to extract parameters."""
        param_descriptions = "\n".join(
            f"- {p.name}: {p.description} (type: {p.type})"
            for p in tool.parameters
            if p.name in missing_params
        )

        prompt = (
            f"Task: {task}\n\n"
            f"Tool: {tool.name}\n"
            f"Missing parameters:\n{param_descriptions}\n\n"
            "Extract values for the missing parameters from the task. "
            "Respond with JSON:\n"
            '{"param_name": "value", ...}'
        )

        try:
            response = await self._llm_matcher(prompt)
            import json
            return json.loads(response)
        except Exception as exc:
            logger.warning("LLM parameter extraction parsing failed: %s", exc)
            return {}

    async def execute_tool(
        self,
        tool_id: str,
        parameters: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> ToolExecution:
        """Execute a tool with parameters.

        Args:
            tool_id: ID of the tool to execute
            parameters: Tool parameters
            timeout: Optional execution timeout

        Returns:
            Execution record
        """
        tool = self._tools.get(tool_id)
        if not tool:
            execution = ToolExecution(
                tool_id=tool_id,
                tool_name="unknown",
                parameters=parameters,
                status=ExecutionStatus.FAILED,
                error="Tool not found",
            )
            self._executions.append(execution)
            return execution

        if tool.status != ToolStatus.AVAILABLE:
            execution = ToolExecution(
                tool_id=tool_id,
                tool_name=tool.name,
                parameters=parameters,
                status=ExecutionStatus.FAILED,
                error=f"Tool is {tool.status.value}",
            )
            self._executions.append(execution)
            return execution

        # Validate parameters
        validation_error = self._validate_parameters(tool, parameters)
        if validation_error:
            execution = ToolExecution(
                tool_id=tool_id,
                tool_name=tool.name,
                parameters=parameters,
                status=ExecutionStatus.FAILED,
                error=validation_error,
            )
            self._executions.append(execution)
            return execution

        # Create execution record
        execution = ToolExecution(
            tool_id=tool_id,
            tool_name=tool.name,
            parameters=parameters,
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        self._executions.append(execution)

        # Execute the tool
        timeout = timeout or tool.timeout
        start_time = asyncio.get_event_loop().time()

        try:
            if tool.handler:
                if asyncio.iscoroutinefunction(tool.handler):
                    result = await asyncio.wait_for(
                        tool.handler(**parameters),
                        timeout=timeout,
                    )
                else:
                    result = await asyncio.to_thread(
                        tool.handler,
                        **parameters,
                    )
            else:
                raise ValueError("Tool has no handler")

            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000
            execution.status = ExecutionStatus.COMPLETED
            execution.result = result
            execution.completed_at = datetime.now(timezone.utc)
            execution.execution_time_ms = execution_time

            # Update tool statistics
            tool.execution_count += 1
            tool.success_count += 1
            tool.last_executed = datetime.now(timezone.utc)

            logger.info(
                "Executed tool %s in %.2fms",
                tool.name,
                execution_time,
            )

        except asyncio.TimeoutError:
            execution.status = ExecutionStatus.TIMEOUT
            execution.error = "Execution timeout"
            execution.completed_at = datetime.now(timezone.utc)
            execution.execution_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            tool.execution_count += 1
            logger.warning("Tool %s execution timed out", tool.name)

        except Exception as exc:
            execution.status = ExecutionStatus.FAILED
            execution.error = str(exc)
            execution.completed_at = datetime.now(timezone.utc)
            execution.execution_time_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            tool.execution_count += 1
            logger.error("Tool %s execution failed: %s", tool.name, exc)

        return execution

    def _validate_parameters(self, tool: Tool, parameters: Dict[str, Any]) -> Optional[str]:
        """Validate parameters against tool definition."""
        for param in tool.parameters:
            if param.required and param.name not in parameters:
                return f"Missing required parameter: {param.name}"

            if param.name in parameters:
                value = parameters[param.name]
                # Basic type checking
                if param.type != "any":
                    expected_type = param.type
                    actual_type = type(value).__name__
                    if actual_type != expected_type:
                        # Allow some flexibility
                        if not self._is_type_compatible(value, expected_type):
                            return f"Parameter {param.name} has wrong type: expected {expected_type}, got {actual_type}"

        return None

    def _is_type_compatible(self, value: Any, expected_type: str) -> bool:
        """Check if value is compatible with expected type."""
        type_map = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        }

        expected = type_map.get(expected_type)
        if expected:
            return isinstance(value, expected)

        return True

    def evaluate_result(
        self,
        execution: ToolExecution,
        expected_output: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Evaluate the quality of a tool execution result.

        Args:
            execution: The execution to evaluate
            expected_output: Optional expected output for comparison

        Returns:
            Evaluation metrics
        """
        evaluation = {
            "success": execution.status == ExecutionStatus.COMPLETED,
            "execution_time_ms": execution.execution_time_ms,
            "has_result": execution.result is not None,
            "has_error": execution.error is not None,
        }

        if expected_output is not None and execution.result is not None:
            evaluation["matches_expected"] = execution.result == expected_output

        return evaluation

    def get_execution_history(
        self,
        tool_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ToolExecution]:
        """Get execution history.

        Args:
            tool_id: Optional tool ID filter
            limit: Maximum number of executions

        Returns:
            List of executions
        """
        executions = self._executions

        if tool_id:
            executions = [e for e in executions if e.tool_id == tool_id]

        # Sort by started_at (most recent first)
        executions.sort(key=lambda e: e.started_at or datetime.min, reverse=True)

        return executions[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get tool selector statistics."""
        return {
            "total_tools": len(self._tools),
            "available_tools": len([t for t in self._tools.values() if t.status == ToolStatus.AVAILABLE]),
            "total_executions": len(self._executions),
            "successful_executions": len([e for e in self._executions if e.status == ExecutionStatus.COMPLETED]),
            "failed_executions": len([e for e in self._executions if e.status == ExecutionStatus.FAILED]),
            "total_categories": len(self._category_index),
        }
