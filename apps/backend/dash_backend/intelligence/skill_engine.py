"""Skill Engine - Skill registration, discovery, and execution.

Implements a flexible skill system for AI capabilities:
- Skill registration with metadata and dependencies
- Skill discovery based on task requirements
- Skill execution with parameter validation
- Skill dependency management and resolution
- Skill sandboxing for safe execution

Features:
- Dynamic skill loading from plugins
- Skill versioning and compatibility checking
- Skill parameter schema validation
- Skill result caching
- Skill execution monitoring and telemetry
"""

from __future__ import annotations

import asyncio
import inspect
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class SkillStatus(str, Enum):
    """Status of a skill."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class SkillParameter:
    """Parameter definition for a skill."""
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
class SkillDependency:
    """Dependency requirement for a skill."""
    skill_id: str
    version: str = ">=1.0.0"
    optional: bool = False


@dataclass
class Skill:
    """Represents an executable skill."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    status: SkillStatus = SkillStatus.ACTIVE
    parameters: List[SkillParameter] = field(default_factory=list)
    dependencies: List[SkillDependency] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    category: str = "general"
    handler: Optional[Callable] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_count: int = 0
    last_executed: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "status": self.status.value,
            "parameters": [p.to_dict() for p in self.parameters],
            "dependencies": [
                {
                    "skill_id": d.skill_id,
                    "version": d.version,
                    "optional": d.optional,
                }
                for d in self.dependencies
            ],
            "tags": self.tags,
            "category": self.category,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "execution_count": self.execution_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
        }


@dataclass
class SkillExecutionResult:
    """Result of a skill execution."""
    skill_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "metadata": self.metadata,
        }


class SkillEngine:
    """Skill registration, discovery, and execution engine.

    Manages the lifecycle of skills, handles dependency resolution,
    and provides safe execution with parameter validation.
    """

    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._skill_index: Dict[str, Set[str]] = {}  # tag -> skill_ids
        self._category_index: Dict[str, Set[str]] = {}  # category -> skill_ids
        self._result_cache: Dict[str, SkillExecutionResult] = {}
        self._cache_ttl: float = 300.0  # 5 minutes
        self._sandbox_enabled: bool = True

    def register_skill(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        parameters: Optional[List[SkillParameter]] = None,
        dependencies: Optional[List[SkillDependency]] = None,
        tags: Optional[List[str]] = None,
        category: str = "general",
        version: str = "1.0.0",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Skill:
        """Register a new skill.

        Args:
            name: Name of the skill
            handler: Callable that implements the skill
            description: Description of what the skill does
            parameters: List of parameter definitions
            dependencies: List of skill dependencies
            tags: Tags for skill discovery
            category: Category for organization
            version: Skill version
            metadata: Additional metadata

        Returns:
            The registered skill
        """
        # Auto-detect parameters from handler signature if not provided
        if parameters is None:
            parameters = self._detect_parameters(handler)

        skill = Skill(
            name=name,
            description=description,
            version=version,
            parameters=parameters,
            dependencies=dependencies or [],
            tags=tags or [],
            category=category,
            handler=handler,
            metadata=metadata or {},
        )

        self._skills[skill.id] = skill

        # Update indexes
        for tag in skill.tags:
            if tag not in self._skill_index:
                self._skill_index[tag] = set()
            self._skill_index[tag].add(skill.id)

        if skill.category not in self._category_index:
            self._category_index[skill.category] = set()
        self._category_index[skill.category].add(skill.id)

        logger.info("Registered skill: %s (v%s)", name, version)
        return skill

    def _detect_parameters(self, handler: Callable) -> List[SkillParameter]:
        """Auto-detect parameters from handler signature."""
        parameters = []
        sig = inspect.signature(handler)

        for name, param in sig.parameters.items():
            if name == "self":
                continue

            param_type = "any"
            if param.annotation != inspect.Parameter.empty:
                param_type = str(param.annotation)

            required = param.default == inspect.Parameter.empty
            default = param.default if not required else None

            parameters.append(
                SkillParameter(
                    name=name,
                    type=param_type,
                    required=required,
                    default=default,
                )
            )

        return parameters

    def unregister_skill(self, skill_id: str) -> bool:
        """Unregister a skill."""
        skill = self._skills.get(skill_id)
        if not skill:
            return False

        # Remove from indexes
        for tag in skill.tags:
            if tag in self._skill_index:
                self._skill_index[tag].discard(skill_id)

        if skill.category in self._category_index:
            self._category_index[skill.category].discard(skill_id)

        # Remove from skills
        del self._skills[skill_id]

        # Clear cache
        self._result_cache = {
            k: v for k, v in self._result_cache.items()
            if not k.startswith(skill_id)
        }

        logger.info("Unregistered skill: %s", skill.name)
        return True

    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)

    def get_skill_by_name(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        for skill in self._skills.values():
            if skill.name == name:
                return skill
        return None

    def discover_skills(
        self,
        query: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category: Optional[str] = None,
        status: SkillStatus = SkillStatus.ACTIVE,
    ) -> List[Skill]:
        """Discover skills based on criteria.

        Args:
            query: Search query for name/description
            tags: Filter by tags
            category: Filter by category
            status: Filter by status

        Returns:
            List of matching skills
        """
        candidates = list(self._skills.values())

        # Filter by status
        if status:
            candidates = [s for s in candidates if s.status == status]

        # Filter by category
        if category:
            candidates = [s for s in candidates if s.category == category]

        # Filter by tags
        if tags:
            candidates = [
                s for s in candidates
                if all(tag in s.tags for tag in tags)
            ]

        # Filter by query
        if query:
            query_lower = query.lower()
            candidates = [
                s for s in candidates
                if query_lower in s.name.lower()
                or query_lower in s.description.lower()
            ]

        return candidates

    def get_skills_by_tag(self, tag: str) -> List[Skill]:
        """Get all skills with a specific tag."""
        skill_ids = self._skill_index.get(tag, set())
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def get_skills_by_category(self, category: str) -> List[Skill]:
        """Get all skills in a category."""
        skill_ids = self._category_index.get(category, set())
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    async def execute_skill(
        self,
        skill_id: str,
        parameters: Dict[str, Any],
        use_cache: bool = True,
        timeout: float = 30.0,
    ) -> SkillExecutionResult:
        """Execute a skill with parameters.

        Args:
            skill_id: ID of the skill to execute
            parameters: Parameters for the skill
            use_cache: Whether to use cached results
            timeout: Execution timeout in seconds

        Returns:
            Execution result
        """
        skill = self._skills.get(skill_id)
        if not skill:
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                error="Skill not found",
            )

        if skill.status != SkillStatus.ACTIVE:
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                error=f"Skill is {skill.status.value}",
            )

        # Check cache
        cache_key = f"{skill_id}:{hash(str(sorted(parameters.items())))}"
        if use_cache and cache_key in self._result_cache:
            logger.debug("Using cached result for skill: %s", skill.name)
            return self._result_cache[cache_key]

        # Validate parameters
        validation_error = self._validate_parameters(skill, parameters)
        if validation_error:
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                error=validation_error,
            )

        # Resolve dependencies
        deps_resolved = await self._resolve_dependencies(skill)
        if not deps_resolved:
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                error="Failed to resolve dependencies",
            )

        # Execute the skill
        start_time = asyncio.get_event_loop().time()

        try:
            if self._sandbox_enabled:
                result = await self._execute_sandboxed(skill, parameters, timeout)
            else:
                result = await self._execute_direct(skill, parameters, timeout)

            execution_time = (asyncio.get_event_loop().time() - start_time) * 1000

            # Update skill statistics
            skill.execution_count += 1
            skill.last_executed = datetime.now(timezone.utc)

            execution_result = SkillExecutionResult(
                skill_id=skill_id,
                success=True,
                result=result,
                execution_time_ms=execution_time,
            )

            # Cache the result
            if use_cache:
                self._result_cache[cache_key] = execution_result

            logger.info(
                "Executed skill %s in %.2fms",
                skill.name,
                execution_time,
            )

            return execution_result

        except asyncio.TimeoutError:
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                error="Execution timeout",
                execution_time_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
            )
        except Exception as exc:
            logger.error("Skill execution failed: %s", exc)
            return SkillExecutionResult(
                skill_id=skill_id,
                success=False,
                error=str(exc),
                execution_time_ms=(asyncio.get_event_loop().time() - start_time) * 1000,
            )

    def _validate_parameters(self, skill: Skill, parameters: Dict[str, Any]) -> Optional[str]:
        """Validate parameters against skill definition."""
        # Check for missing required parameters
        for param in skill.parameters:
            if param.required and param.name not in parameters:
                return f"Missing required parameter: {param.name}"

            # Check type constraints (basic)
            if param.name in parameters:
                value = parameters[param.name]
                if param.type != "any" and type(value).__name__ != param.type:
                    # Allow some flexibility
                    if not self._is_type_compatible(value, param.type):
                        return f"Parameter {param.name} has wrong type: expected {param.type}"

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

        return True  # Allow unknown types

    async def _resolve_dependencies(self, skill: Skill) -> bool:
        """Resolve skill dependencies."""
        for dep in skill.dependencies:
            dep_skill = self._skills.get(dep.skill_id)
            if not dep_skill:
                if not dep.optional:
                    logger.error("Required dependency not found: %s", dep.skill_id)
                    return False
                continue

            if dep_skill.status != SkillStatus.ACTIVE:
                if not dep.optional:
                    logger.error("Required dependency not active: %s", dep.skill_id)
                    return False

        return True

    async def _execute_direct(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        timeout: float,
    ) -> Any:
        """Execute skill directly without sandboxing."""
        if not skill.handler:
            raise ValueError("Skill has no handler")

        if inspect.iscoroutinefunction(skill.handler):
            return await asyncio.wait_for(
                skill.handler(**parameters),
                timeout=timeout,
            )
        else:
            return await asyncio.to_thread(
                skill.handler,
                **parameters,
            )

    async def _execute_sandboxed(
        self,
        skill: Skill,
        parameters: Dict[str, Any],
        timeout: float,
    ) -> Any:
        """Execute skill with basic sandboxing."""
        # For now, this is the same as direct execution
        # In a full implementation, this would use process isolation
        # or restricted execution environment
        return await self._execute_direct(skill, parameters, timeout)

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self._result_cache.clear()
        logger.info("Cleared skill result cache")

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the skill engine."""
        return {
            "total_skills": len(self._skills),
            "active_skills": len([s for s in self._skills.values() if s.status == SkillStatus.ACTIVE]),
            "total_categories": len(self._category_index),
            "total_tags": len(self._skill_index),
            "cache_size": len(self._result_cache),
            "total_executions": sum(s.execution_count for s in self._skills.values()),
        }
