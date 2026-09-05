"""Streaming service for AI responses with retry system and token budgeting."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator, Dict, List, Optional
from dataclasses import dataclass, field

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_router.router import get_ai_router

logger = get_logger(__name__)


@dataclass
class TokenBudget:
    """Token budget for a request."""
    max_tokens: int
    used_tokens: int = 0
    reserved_tokens: int = 0
    
    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.used_tokens - self.reserved_tokens)
    
    def reserve(self, tokens: int) -> bool:
        """Reserve tokens if available."""
        if self.remaining_tokens >= tokens:
            self.reserved_tokens += tokens
            return True
        return False
    
    def use_reserved(self, tokens: int) -> None:
        """Use reserved tokens."""
        used = min(tokens, self.reserved_tokens)
        self.reserved_tokens -= used
        self.used_tokens += used
    
    def use(self, tokens: int) -> bool:
        """Use tokens directly if available."""
        if self.remaining_tokens >= tokens:
            self.used_tokens += tokens
            return True
        return False


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 10.0
    backoff_multiplier: float = 2.0
    retryable_errors: List[str] = field(default_factory=lambda: [
        "timeout",
        "connection",
        "network",
        "temporary",
        "rate limit",
    ])


class StreamingService:
    """Service for streaming AI responses with retry and timeout handling."""
    
    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        default_timeout: float = 30.0,
        default_max_tokens: int = 4096,
    ):
        self.retry_config = retry_config or RetryConfig()
        self.default_timeout = default_timeout
        self.default_max_tokens = default_max_tokens
        self.ai_router = get_ai_router()
        
    async def stream_response(
        self,
        query: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        force_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[str]:
        """Stream a response with retry logic and timeout handling.
        
        Args:
            query: The user's query
            messages: Conversation messages
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            force_model: Force a specific model
            context: Additional context
            
        Yields:
            Response tokens as they are generated
        """
        max_tokens = max_tokens or self.default_max_tokens
        timeout = timeout or self.default_timeout
        budget = TokenBudget(max_tokens=max_tokens)
        
        last_error: Optional[Exception] = None
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                async for token in self._stream_with_timeout(
                    query=query,
                    messages=messages,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=budget.remaining_tokens,
                    force_model=force_model,
                    context=context,
                    timeout=timeout,
                    budget=budget,
                ):
                    yield token
                
                # Success - break out of retry loop
                return
                
            except Exception as e:
                last_error = e
                logger.warning(
                    "Stream attempt %d failed: %s",
                    attempt + 1,
                    e,
                )
                
                # Check if error is retryable
                if not self._is_retryable_error(e):
                    logger.error("Non-retryable error: %s", e)
                    raise
                
                # Don't wait after last attempt
                if attempt < self.retry_config.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.info("Retrying after %.2f seconds", delay)
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_error or RuntimeError("Streaming failed after all retries")
    
    async def _stream_with_timeout(
        self,
        query: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int,
        force_model: Optional[str],
        context: Optional[Dict[str, Any]],
        timeout: float,
        budget: TokenBudget,
    ) -> AsyncIterator[str]:
        """Stream with timeout and token budgeting."""
        start_time = time.time()
        token_count = 0
        
        try:
            async for token in self.ai_router.route_streaming(
                query=query,
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                force_model=force_model,
                context=context,
            ):
                # Check timeout
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Streaming timeout after {timeout}s")
                
                # Check token budget
                estimated_tokens = len(token.split())  # Rough estimate
                if not budget.use(estimated_tokens):
                    logger.warning("Token budget exhausted")
                    break
                
                token_count += estimated_tokens
                yield token
                
        except asyncio.CancelledError:
            logger.info("Streaming cancelled by user")
            raise
        except Exception as e:
            logger.error("Streaming error: %s", e)
            raise
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        error_str = str(error).lower()
        for retryable in self.retry_config.retryable_errors:
            if retryable in error_str:
                return True
        return False
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        delay = self.retry_config.initial_delay * (
            self.retry_config.backoff_multiplier ** attempt
        )
        return min(delay, self.retry_config.max_delay)
    
    async def stream_with_summarization(
        self,
        query: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        force_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        summarize_threshold: int = 2000,
    ) -> AsyncIterator[str]:
        """Stream with automatic summarization for long responses.
        
        Streams the full response; if it exceeds summarize_threshold tokens,
        a concise LLM-generated summary is appended afterwards so callers
        always get the complete answer plus a digest.
        """
        max_tokens = max_tokens or self.default_max_tokens
        timeout = timeout or self.default_timeout
        budget = TokenBudget(max_tokens=max_tokens)
        
        full_response = []
        token_count = 0
        
        async for token in self.stream_response(
            query=query,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            force_model=force_model,
            context=context,
        ):
            full_response.append(token)
            token_count += len(token.split())
            
            # Yield tokens as they come
            yield token
        
        # Summarize only after the complete response has been streamed so we
        # never truncate the answer mid-stream.
        if token_count > summarize_threshold:
            logger.info(
                "Response exceeds threshold (%d tokens), appending summary",
                token_count,
            )
            response_text = "".join(full_response)
            try:
                summary = await self.get_non_streaming_response(
                    query=(
                        "Summarize the following response in at most 5 bullet "
                        f"points:\n\n{response_text[:8000]}"
                    ),
                    messages=[],
                    system_prompt="You produce concise, accurate summaries.",
                    temperature=0.3,
                    max_tokens=min(400, max_tokens),
                    timeout=timeout,
                    force_model=force_model,
                )
                if summary and summary.strip():
                    yield f"\n\n--- SUMMARY ---\n{summary.strip()}\n--- END SUMMARY ---"
            except Exception as exc:
                logger.warning("Post-stream summarization failed: %s", exc)
    
    async def get_non_streaming_response(
        self,
        query: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
        force_model: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Get a non-streaming response with retry logic."""
        max_tokens = max_tokens or self.default_max_tokens
        timeout = timeout or self.default_timeout
        
        # Collect streaming response into a string
        response_parts = []
        async for token in self.stream_response(
            query=query,
            messages=messages,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            force_model=force_model,
            context=context,
        ):
            response_parts.append(token)
        
        return "".join(response_parts)


# Singleton
_streaming_service: Optional[StreamingService] = None


def get_streaming_service() -> StreamingService:
    global _streaming_service
    if _streaming_service is None:
        _streaming_service = StreamingService()
    return _streaming_service
