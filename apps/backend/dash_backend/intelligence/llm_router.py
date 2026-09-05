"""LLM Router - Model selection and automatic routing.

Implements intelligent LLM routing:
- Model selection (OpenAI, Claude, Gemini, Ollama)
- Automatic routing based on task requirements
- Fallback logic for reliability
- Model capabilities tracking

Features:
- Multi-provider support
- Task-based model selection
- Automatic fallback on failure
- Cost optimization
- Latency monitoring
- Capability matching
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


class Provider(str, Enum):
    """LLM providers."""
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    OLLAMA = "ollama"


class ModelCapability(str, Enum):
    """Model capabilities."""
    CHAT = "chat"
    CODE_GENERATION = "code_generation"
    REASONING = "reasoning"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"


@dataclass
class ModelInfo:
    """Information about an LLM model."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    provider: Provider = Provider.OPENAI
    capabilities: List[ModelCapability] = field(default_factory=list)
    context_window: int = 4096
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    latency_ms: float = 0.0
    reliability: float = 1.0  # 0-1 score
    available: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider.value,
            "capabilities": [c.value for c in self.capabilities],
            "context_window": self.context_window,
            "max_tokens": self.max_tokens,
            "cost_per_1k_input": self.cost_per_1k_input,
            "cost_per_1k_output": self.cost_per_1k_output,
            "latency_ms": self.latency_ms,
            "reliability": self.reliability,
            "available": self.available,
            "metadata": self.metadata,
        }


@dataclass
class RoutingDecision:
    """Result of model routing."""
    model: ModelInfo
    reason: str = ""
    fallback_chain: List[ModelInfo] = field(default_factory=list)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model.to_dict(),
            "reason": self.reason,
            "fallback_chain": [m.to_dict() for m in self.fallback_chain],
            "confidence": self.confidence,
        }


@dataclass
class LLMRequest:
    """An LLM request."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[Dict[str, str]] = field(default_factory=list)
    required_capabilities: List[ModelCapability] = field(default_factory=list)
    preferred_provider: Optional[Provider] = None
    max_tokens: Optional[int] = None
    temperature: float = 0.7
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """An LLM response."""
    request_id: str = ""
    model_name: str = ""
    content: str = ""
    tokens_used: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "model_name": self.model_name,
            "content": self.content,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }


class LLMRouter:
    """LLM model selection and routing engine.

    Routes requests to appropriate models based on capabilities,
    cost, latency, and reliability with automatic fallback.
    """

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._provider_handlers: Dict[Provider, Callable] = {}
        self._request_history: List[Dict[str, Any]] = []
        self._default_provider = Provider.OLLAMA
        self._enable_fallback = True
        self._max_fallback_attempts = 3

        # Initialize default models
        self._initialize_default_models()

    def _initialize_default_models(self) -> None:
        """Initialize default model configurations."""
        # OpenAI models
        self._models["gpt-4o"] = ModelInfo(
            name="gpt-4o",
            provider=Provider.OPENAI,
            capabilities=[
                ModelCapability.CHAT,
                ModelCapability.CODE_GENERATION,
                ModelCapability.REASONING,
                ModelCapability.VISION,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.STREAMING,
                ModelCapability.JSON_MODE,
            ],
            context_window=128000,
            max_tokens=4096,
            cost_per_1k_input=0.005,
            cost_per_1k_output=0.015,
            reliability=0.99,
        )

        self._models["gpt-4o-mini"] = ModelInfo(
            name="gpt-4o-mini",
            provider=Provider.OPENAI,
            capabilities=[
                ModelCapability.CHAT,
                ModelCapability.CODE_GENERATION,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.STREAMING,
                ModelCapability.JSON_MODE,
            ],
            context_window=128000,
            max_tokens=16384,
            cost_per_1k_input=0.00015,
            cost_per_1k_output=0.0006,
            reliability=0.98,
        )

        # Claude models
        self._models["claude-3-5-sonnet"] = ModelInfo(
            name="claude-3-5-sonnet",
            provider=Provider.CLAUDE,
            capabilities=[
                ModelCapability.CHAT,
                ModelCapability.CODE_GENERATION,
                ModelCapability.REASONING,
                ModelCapability.VISION,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.STREAMING,
            ],
            context_window=200000,
            max_tokens=8192,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
            reliability=0.99,
        )

        # Gemini models
        self._models["gemini-1.5-pro"] = ModelInfo(
            name="gemini-1.5-pro",
            provider=Provider.GEMINI,
            capabilities=[
                ModelCapability.CHAT,
                ModelCapability.CODE_GENERATION,
                ModelCapability.REASONING,
                ModelCapability.VISION,
                ModelCapability.FUNCTION_CALLING,
                ModelCapability.STREAMING,
            ],
            context_window=1000000,
            max_tokens=8192,
            cost_per_1k_input=0.00125,
            cost_per_1k_output=0.005,
            reliability=0.97,
        )

        # Ollama models (placeholder)
        self._models["llama3.2:3b"] = ModelInfo(
            name="llama3.2:3b",
            provider=Provider.OLLAMA,
            capabilities=[
                ModelCapability.CHAT,
                ModelCapability.CODE_GENERATION,
                ModelCapability.REASONING,
                ModelCapability.STREAMING,
            ],
            context_window=128000,
            max_tokens=4096,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0,
            reliability=0.95,
        )

        logger.info("Initialized %d default models", len(self._models))

    def register_provider_handler(self, provider: Provider, handler: Callable) -> None:
        """Register a handler for a provider."""
        self._provider_handlers[provider] = handler
        logger.info("Registered handler for provider: %s", provider.value)

    def register_model(self, model: ModelInfo) -> None:
        """Register a new model."""
        self._models[model.name] = model
        logger.info("Registered model: %s (%s)", model.name, model.provider.value)

    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get a model by name."""
        return self._models.get(model_name)

    def get_models_by_provider(self, provider: Provider) -> List[ModelInfo]:
        """Get all models for a provider."""
        return [m for m in self._models.values() if m.provider == provider]

    def get_models_by_capability(self, capability: ModelCapability) -> List[ModelInfo]:
        """Get models with a specific capability."""
        return [m for m in self._models.values() if capability in m.capabilities]

    async def route(
        self,
        request: LLMRequest,
    ) -> RoutingDecision:
        """Route a request to the best model.

        Args:
            request: The LLM request

        Returns:
            Routing decision with selected model and fallback chain
        """
        # Filter models by required capabilities
        candidates = []
        for model in self._models.values():
            if not model.available:
                continue

            # Check if model has all required capabilities
            has_capabilities = all(cap in model.capabilities for cap in request.required_capabilities)
            if not has_capabilities:
                continue

            # Check context window
            estimated_tokens = sum(len(m.get("content", "")) // 4 for m in request.messages)
            if estimated_tokens > model.context_window:
                continue

            candidates.append(model)

        if not candidates:
            # Fallback to any available model
            candidates = [m for m in self._models.values() if m.available]
            if not candidates:
                raise ValueError("No available models")

        # If preferred provider is specified, prioritize it
        if request.preferred_provider:
            provider_candidates = [m for m in candidates if m.provider == request.preferred_provider]
            if provider_candidates:
                candidates = provider_candidates

        # Score candidates based on multiple factors
        scored = []
        for model in candidates:
            score = self._score_model(model, request)
            scored.append((model, score))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Select best model
        best_model, best_score = scored[0] if scored else (candidates[0], 0.5)

        # Build fallback chain
        fallback_chain = [m for m, _ in scored[1:self._max_fallback_attempts]]

        # Generate reason
        reason = self._generate_routing_reason(best_model, request)

        logger.info(
            "Routed request to %s (score: %.2f, fallbacks: %d)",
            best_model.name,
            best_score,
            len(fallback_chain),
        )

        return RoutingDecision(
            model=best_model,
            reason=reason,
            fallback_chain=fallback_chain,
            confidence=best_score,
        )

    def _score_model(self, model: ModelInfo, request: LLMRequest) -> float:
        """Score a model for a request."""
        score = 0.0

        # Reliability (weight: 0.4)
        score += model.reliability * 0.4

        # Latency (inverse, weight: 0.2)
        if model.latency_ms > 0:
            latency_score = 1.0 / (1.0 + model.latency_ms / 1000.0)
            score += latency_score * 0.2

        # Cost (inverse, weight: 0.2)
        total_cost = model.cost_per_1k_input + model.cost_per_1k_output
        if total_cost > 0:
            cost_score = 1.0 / (1.0 + total_cost * 10)
            score += cost_score * 0.2
        else:
            score += 0.2  # Free models get full points

        # Capability match (weight: 0.2)
        if request.required_capabilities:
            matched = sum(1 for cap in request.required_capabilities if cap in model.capabilities)
            capability_score = matched / len(request.required_capabilities)
            score += capability_score * 0.2

        return score

    def _generate_routing_reason(self, model: ModelInfo, request: LLMRequest) -> str:
        """Generate a reason for the routing decision."""
        reasons = []

        if request.preferred_provider and model.provider == request.preferred_provider:
            reasons.append(f"Matches preferred provider ({model.provider.value})")

        reasons.append(f"Reliability: {model.reliability:.2f}")

        if model.latency_ms > 0:
            reasons.append(f"Latency: {model.latency_ms:.0f}ms")

        if model.cost_per_1k_input > 0 or model.cost_per_1k_output > 0:
            reasons.append(f"Cost: ${model.cost_per_1k_input + model.cost_per_1k_output:.4f}/1k tokens")

        return "; ".join(reasons)

    async def execute(
        self,
        request: LLMRequest,
        routing: Optional[RoutingDecision] = None,
    ) -> LLMResponse:
        """Execute an LLM request with routing and fallback.

        Args:
            request: The LLM request
            routing: Optional pre-computed routing decision

        Returns:
            LLM response
        """
        if not routing:
            routing = await self.route(request)

        # Try primary model
        response = await self._execute_with_model(request, routing.model)

        if response.success or not self._enable_fallback:
            return response

        # Try fallback models
        for fallback_model in routing.fallback_chain:
            logger.warning(
                "Primary model %s failed, trying fallback: %s",
                routing.model.name,
                fallback_model.name,
            )
            response = await self._execute_with_model(request, fallback_model)
            if response.success:
                return response

        # All models failed
        return response

    async def _execute_with_model(
        self,
        request: LLMRequest,
        model: ModelInfo,
    ) -> LLMResponse:
        """Execute a request with a specific model."""
        handler = self._provider_handlers.get(model.provider)
        if not handler:
            return LLMResponse(
                request_id=request.id,
                model_name=model.name,
                success=False,
                error=f"No handler for provider: {model.provider.value}",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            result = await asyncio.wait_for(
                handler(
                    model_name=model.name,
                    messages=request.messages,
                    max_tokens=request.max_tokens or model.max_tokens,
                    temperature=request.temperature,
                ),
                timeout=request.timeout,
            )

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            # Update model latency
            model.latency_ms = (model.latency_ms * 0.9) + (latency_ms * 0.1)

            return LLMResponse(
                request_id=request.id,
                model_name=model.name,
                content=result.get("content", ""),
                tokens_used=result.get("tokens_used", 0),
                latency_ms=latency_ms,
                success=True,
            )

        except asyncio.TimeoutError:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            model.reliability = max(0.0, model.reliability - 0.1)
            return LLMResponse(
                request_id=request.id,
                model_name=model.name,
                success=False,
                error="Execution timeout",
                latency_ms=latency_ms,
            )

        except Exception as exc:
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            model.reliability = max(0.0, model.reliability - 0.1)
            return LLMResponse(
                request_id=request.id,
                model_name=model.name,
                success=False,
                error=str(exc),
                latency_ms=latency_ms,
            )

    def set_model_availability(self, model_name: str, available: bool) -> bool:
        """Set the availability of a model."""
        model = self._models.get(model_name)
        if model:
            model.available = available
            logger.info("Set model %s availability to: %s", model_name, available)
            return True
        return False

    def update_model_reliability(self, model_name: str, success: bool) -> None:
        """Update model reliability based on execution result."""
        model = self._models.get(model_name)
        if model:
            if success:
                model.reliability = min(1.0, model.reliability + 0.01)
            else:
                model.reliability = max(0.0, model.reliability - 0.05)

    def get_statistics(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "total_models": len(self._models),
            "available_models": len([m for m in self._models.values() if m.available]),
            "by_provider": {
                provider.value: len([m for m in self._models.values() if m.provider == provider])
                for provider in Provider
            },
            "total_requests": len(self._request_history),
            "fallback_enabled": self._enable_fallback,
        }
