"""AI Router - Automatic model selection based on task type."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_providers.provider_manager import get_provider_manager
from dash_backend.services.ai_providers.base import CompletionRequest, CompletionResponse

logger = get_logger(__name__)


class TaskType(Enum):
    """Types of AI tasks."""
    CHAT = "chat"
    CODING = "coding"
    REASONING = "reasoning"
    FAST = "fast"
    EMBEDDING = "embeddings"


class ModelMapping:
    """Maps task types to specific models."""
    
    # Default model mappings
    DEFAULT_MODELS = {
        TaskType.CHAT: "llama3.2:3b",
        TaskType.CODING: "llama3.2:3b",
        TaskType.REASONING: "llama3.2:3b",
        TaskType.FAST: "llama3.2:3b",
        TaskType.EMBEDDINGS: "nomic-embed-text",
    }
    
    def __init__(self, custom_mappings: Optional[Dict[TaskType, str]] = None):
        self.mappings = custom_mappings or self.DEFAULT_MODELS.copy()
    
    def get_model(self, task_type: TaskType) -> str:
        """Get the model for a given task type."""
        return self.mappings.get(task_type, self.DEFAULT_MODELS[task_type])
    
    def set_model(self, task_type: TaskType, model: str) -> None:
        """Set a custom model for a task type."""
        self.mappings[task_type] = model


class TaskClassifier:
    """Classifies user queries into task types."""
    
    # Patterns for different task types
    CODING_PATTERNS = [
        r"code", r"function", r"class", r"debug", r"fix", r"implement",
        r"write.*code", r"programming", r"algorithm", r"script", r"api",
        r"refactor", r"optimize.*code", r"test", r"build", r"compile",
    ]
    
    REASONING_PATTERNS = [
        r"why", r"how.*work", r"explain", r"analyze", r"compare",
        r"reason", r"logic", r"step.*step", r"think", r"consider",
        r"evaluate", r"assess", r"determine", r"conclude",
    ]
    
    FAST_PATTERNS = [
        r"yes|no", r"true|false", r"short", r"quick", r"brief",
        r"summarize.*short", r"one.*word", r"simple.*answer",
    ]
    
    @classmethod
    def classify(cls, query: str, context: Optional[Dict[str, Any]] = None) -> TaskType:
        """Classify a query into a task type."""
        query_lower = query.lower()
        
        # Check coding patterns
        if any(re.search(pattern, query_lower) for pattern in cls.CODING_PATTERNS):
            return TaskType.CODING
        
        # Check reasoning patterns
        if any(re.search(pattern, query_lower) for pattern in cls.REASONING_PATTERNS):
            return TaskType.REASONING
        
        # Check fast patterns
        if any(re.search(pattern, query_lower) for pattern in cls.FAST_PATTERNS):
            return TaskType.FAST
        
        # Default to chat
        return TaskType.CHAT


class AIRouter:
    """AI Router for automatic model selection and request routing."""
    
    def __init__(
        self,
        model_mapping: Optional[ModelMapping] = None,
        task_classifier: Optional[TaskClassifier] = None,
    ):
        self.model_mapping = model_mapping or ModelMapping()
        self.task_classifier = task_classifier or TaskClassifier()
        self.provider_manager = get_provider_manager()
        self._request_history: List[Dict[str, Any]] = []
        self._max_history = 100
        
    async def route(
        self,
        query: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        force_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> CompletionResponse:
        """Route a request to the appropriate model.
        
        Args:
            query: The user's query
            messages: Conversation messages
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            force_model: Force a specific model (bypasses routing)
            context: Additional context for classification
            
        Returns:
            CompletionResponse with the result
        """
        # Determine task type
        task_type = self.task_classifier.classify(query, context)
        
        # Get model for task type (or use forced model)
        model = force_model or self.model_mapping.get_model(task_type)
        
        logger.info(
            "Routing request: task_type=%s, model=%s, query=%s",
            task_type.value,
            model,
            query[:100],
        )
        
        # Create completion request
        request = CompletionRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        
        # Update provider to use the selected model
        provider = self.provider_manager.get_provider("ollama")
        if provider:
            provider._config.model = model
        
        # Execute request
        try:
            response = await self.provider_manager.complete(request)
            
            # Record history
            self._record_history(query, task_type, model, response)
            
            return response
        except Exception as e:
            logger.error("Request failed: %s", e)
            # Fallback to default model
            if not force_model:
                logger.info("Falling back to default model")
                return await self.route(
                    query=query,
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    force_model="phi4",
                    context=context,
                )
            raise
    
    async def route_streaming(
        self,
        query: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        force_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Route a streaming request to the appropriate model."""
        task_type = self.task_classifier.classify(query, context)
        model = force_model or self.model_mapping.get_model(task_type)
        
        logger.info(
            "Routing streaming request: task_type=%s, model=%s",
            task_type.value,
            model,
        )
        
        request = CompletionRequest(
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        
        # Update provider to use the selected model
        provider = self.provider_manager.get_provider("ollama")
        if provider:
            provider._config.model = model
        
        async for token in self.provider_manager.complete_streaming(request):
            yield token
    
    def _record_history(
        self,
        query: str,
        task_type: TaskType,
        model: str,
        response: CompletionResponse,
    ) -> None:
        """Record request history for analytics."""
        self._request_history.append({
            "query": query,
            "task_type": task_type.value,
            "model": model,
            "response_length": len(response.content),
            "timestamp": None,  # Will be set if needed
        })
        
        # Trim history
        if len(self._request_history) > self._max_history:
            self._request_history = self._request_history[-self._max_history:]
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get statistics about routing decisions."""
        stats = {
            "total_requests": len(self._request_history),
            "by_task_type": {},
            "by_model": {},
        }
        
        for entry in self._request_history:
            task_type = entry["task_type"]
            model = entry["model"]
            
            stats["by_task_type"][task_type] = stats["by_task_type"].get(task_type, 0) + 1
            stats["by_model"][model] = stats["by_model"].get(model, 0) + 1
        
        return stats
    
    def update_model_mapping(self, task_type: TaskType, model: str) -> None:
        """Update the model mapping for a task type."""
        self.model_mapping.set_model(task_type, model)
        logger.info("Updated model mapping: %s -> %s", task_type.value, model)


# Singleton
_router: Optional[AIRouter] = None


def get_ai_router() -> AIRouter:
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
