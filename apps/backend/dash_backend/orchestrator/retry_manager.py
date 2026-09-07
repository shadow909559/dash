"""Retry Manager - Sophisticated retry logic with exponential backoff and fallback strategies.

Provides configurable retry policies for tool execution, LLM calls, and 
any async operation in the DASH pipeline.
"""

from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, TypeVar

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryStrategy(str, Enum):
    """Available retry strategies."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    CONSTANT_DELAY = "constant_delay"
    IMMEDIATE = "immediate"
    NO_RETRY = "no_retry"


class FallbackStrategy(str, Enum):
    """Available fallback strategies on failure."""
    RETURN_DEFAULT = "return_default"
    RETURN_LAST_RESULT = "return_last_result"
    RAISE_ERROR = "raise_error"
    CALL_FALLBACK_FN = "call_fallback_fn"
    SKIP_AND_CONTINUE = "skip_and_continue"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        strategy: Retry strategy to use.
        base_delay: Base delay in seconds.
        max_delay: Maximum delay in seconds.
        jitter: Add random jitter to delay (True/False).
        retryable_exceptions: Set of exception types that should be retried.
        non_retryable_exceptions: Set of exception types that should NOT be retried.
        on_retry_callback: Optional callback called before each retry.
    """
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True
    retryable_exceptions: Tuple[type, ...] = (Exception,)
    non_retryable_exceptions: Tuple[type, ...] = ()
    on_retry_callback: Optional[Callable[[int, Exception], None]] = None

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        if self.strategy == RetryStrategy.NO_RETRY:
            return 0.0

        if self.strategy == RetryStrategy.IMMEDIATE:
            return 0.0

        if self.strategy == RetryStrategy.CONSTANT_DELAY:
            delay = self.base_delay

        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay * (attempt + 1)

        else:  # EXPONENTIAL_BACKOFF (default)
            delay = self.base_delay * (2 ** attempt)

        # Cap at max_delay
        delay = min(delay, self.max_delay)

        # Add jitter
        if self.jitter and delay > 0:
            delay = delay * (0.5 + random.random() * 0.5)  # 50-100% of calculated delay

        return delay

    def should_retry(self, attempt: int, exception: Exception) -> bool:
        """Determine if the operation should be retried."""
        if attempt >= self.max_retries:
            return False

        # Check non-retryable exceptions
        if self.non_retryable_exceptions and isinstance(exception, self.non_retryable_exceptions):
            return False

        # Check if exception is retryable
        if self.retryable_exceptions and isinstance(exception, self.retryable_exceptions):
            return True

        return False


@dataclass
class RetryResult:
    """Result of a retry operation."""
    success: bool
    result: Optional[Any] = None
    error: Optional[Exception] = None
    attempts: int = 0
    total_delay: float = 0.0
    all_errors: List[Exception] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "attempts": self.attempts,
            "total_delay": self.total_delay,
            "error": str(self.error) if self.error else None,
            "error_count": len(self.all_errors),
        }


DEFAULT_RETRY_POLICY = RetryPolicy(
    max_retries=3,
    strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    base_delay=1.0,
    max_delay=30.0,
    jitter=True,
)


class RetryManager:
    """Manages retry logic for async operations.

    Features:
    - Configurable retry policies per operation type
    - Exponential backoff with jitter
    - Fallback strategies on permanent failure
    - Circuit breaker pattern support
    - Metrics tracking for monitoring
    """

    def __init__(self):
        self._policies: Dict[str, RetryPolicy] = {}
        self._metrics: Dict[str, Dict[str, Any]] = {}

    def register_policy(self, name: str, policy: RetryPolicy) -> None:
        """Register a named retry policy."""
        self._policies[name] = policy
        self._metrics[name] = {"total_attempts": 0, "total_failures": 0, "total_successes": 0}

    def get_policy(self, name: str) -> RetryPolicy:
        """Get a registered retry policy, or the default if not found."""
        return self._policies.get(name, DEFAULT_RETRY_POLICY)

    async def execute_with_retry(
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        policy_name: str = "default",
        policy: Optional[RetryPolicy] = None,
        fallback: Optional[Callable[..., Awaitable[T]]] = None,
        fallback_strategy: FallbackStrategy = FallbackStrategy.RAISE_ERROR,
        default_value: Optional[T] = None,
        **kwargs: Any,
    ) -> T:
        """Execute an async operation with retry logic.

        Args:
            operation: The async function to execute.
            *args: Positional arguments passed to the operation.
            policy_name: Name of the registered retry policy to use.
            policy: Optional inline retry policy (overrides policy_name).
            fallback: Optional fallback function if all retries fail.
            fallback_strategy: Strategy when all retries fail.
            default_value: Default value to return if fallback is RETURN_DEFAULT.
            **kwargs: Keyword arguments passed to the operation.

        Returns:
            The result of the operation, fallback, or default value.

        Raises:
            The last exception if fallback_strategy is RAISE_ERROR and all retries fail.
        """
        active_policy = policy or self.get_policy(policy_name)
        metrics = self._metrics.get(policy_name, {})

        all_errors: List[Exception] = []
        total_delay = 0.0

        for attempt in range(active_policy.max_retries + 1):
            try:
                result = await operation(*args, **kwargs)
                # Success
                metrics["total_attempts"] = metrics.get("total_attempts", 0) + 1
                metrics["total_successes"] = metrics.get("total_successes", 0) + 1
                return result

            except active_policy.non_retryable_exceptions as exc:
                # Non-retryable exception - fail immediately
                logger.warning(
                    "Non-retryable exception in %s: %s",
                    getattr(operation, "__name__", "operation"),
                    exc,
                )
                metrics["total_attempts"] = metrics.get("total_attempts", 0) + 1
                metrics["total_failures"] = metrics.get("total_failures", 0) + 1
                raise

            except Exception as exc:
                all_errors.append(exc)
                metrics["total_attempts"] = metrics.get("total_attempts", 0) + 1

                if not active_policy.should_retry(attempt, exc):
                    logger.warning(
                        "Operation %s failed permanently after %d attempts: %s",
                        getattr(operation, "__name__", "operation"),
                        attempt + 1,
                        exc,
                    )
                    metrics["total_failures"] = metrics.get("total_failures", 0) + 1
                    break

                # Calculate delay
                delay = active_policy.get_delay(attempt)
                total_delay += delay

                logger.info(
                    "Retrying %s (attempt %d/%d) after %.1fs: %s",
                    getattr(operation, "__name__", "operation"),
                    attempt + 1,
                    active_policy.max_retries,
                    delay,
                    exc,
                )

                # Call retry callback
                if active_policy.on_retry_callback:
                    try:
                        active_policy.on_retry_callback(attempt, exc)
                    except Exception:
                        pass

                # Wait before retrying
                await asyncio.sleep(delay)

        # All retries failed - use fallback strategy
        last_error = all_errors[-1] if all_errors else Exception("Operation failed")

        if fallback_strategy == FallbackStrategy.RAISE_ERROR:
            raise last_error

        if fallback_strategy == FallbackStrategy.RETURN_DEFAULT:
            if default_value is not None:
                return default_value
            raise last_error

        if fallback_strategy == FallbackStrategy.CALL_FALLBACK_FN and fallback is not None:
            try:
                return await fallback(*args, **kwargs)
            except Exception as fb_exc:
                logger.error("Fallback function also failed: %s", fb_exc)
                raise last_error

        if fallback_strategy == FallbackStrategy.SKIP_AND_CONTINUE:
            # Return a sentinel/None to indicate skip
            return None  # type: ignore

        raise last_error

    async def execute_with_circuit_breaker(
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        policy_name: str = "default",
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        **kwargs: Any,
    ) -> T:
        """Execute with circuit breaker pattern.

        If the operation fails more than `failure_threshold` times within
        the window, subsequent calls will fail fast for `reset_timeout` seconds.
        """
        metrics = self._metrics.get(policy_name, {})

        # Check if circuit is open
        if metrics.get("circuit_open", False):
            if metrics.get("circuit_open_since", 0) + reset_timeout > asyncio.get_event_loop().time():
                raise RuntimeError("Circuit breaker is open")
            else:
                # Reset circuit
                metrics["circuit_open"] = False
                metrics["circuit_failure_count"] = 0

        try:
            result = await self.execute_with_retry(operation, *args, policy_name=policy_name, **kwargs)
            # Success - reset failure count
            metrics["circuit_failure_count"] = 0
            return result

        except Exception as exc:
            # Increment failure count
            failures = metrics.get("circuit_failure_count", 0) + 1
            metrics["circuit_failure_count"] = failures

            if failures >= failure_threshold:
                metrics["circuit_open"] = True
                metrics["circuit_open_since"] = asyncio.get_event_loop().time()
                logger.warning(
                    "Circuit breaker opened for %s after %d failures",
                    policy_name,
                    failures,
                )

            raise

    def get_metrics(self, policy_name: str) -> Dict[str, Any]:
        """Get retry metrics for a policy."""
        return self._metrics.get(policy_name, {})

    def reset_metrics(self, policy_name: str) -> None:
        """Reset metrics for a policy."""
        if policy_name in self._metrics:
            self._metrics[policy_name] = {"total_attempts": 0, "total_failures": 0, "total_successes": 0}


# Global singleton
_manager: Optional[RetryManager] = None


def get_retry_manager() -> RetryManager:
    """Return the global RetryManager singleton."""
    global _manager
    if _manager is None:
        _manager = RetryManager()
        # Register default policies
        _manager.register_policy("default", DEFAULT_RETRY_POLICY)
        _manager.register_policy("tool_execution", RetryPolicy(
            max_retries=2,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=0.5,
            max_delay=10.0,
            jitter=True,
        ))
        _manager.register_policy("llm_call", RetryPolicy(
            max_retries=3,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            base_delay=1.0,
            max_delay=30.0,
            jitter=True,
        ))
        _manager.register_policy("memory_operation", RetryPolicy(
            max_retries=2,
            strategy=RetryStrategy.CONSTANT_DELAY,
            base_delay=0.1,
            jitter=False,
        ))
        _manager.register_policy("rag_retrieval", RetryPolicy(
            max_retries=2,
            strategy=RetryStrategy.LINEAR_BACKOFF,
            base_delay=0.2,
            max_delay=2.0,
            jitter=True,
        ))
    return _manager
