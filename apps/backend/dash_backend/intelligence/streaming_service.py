"""Streaming Service - Token streaming with interrupt handling.

Implements advanced streaming capabilities:
- Token streaming from LLM responses
- Interrupt handling for user control
- Resume capability for interrupted streams
- Streaming state management

Features:
- Async token streaming
- User interrupt support
- Stream resumption
- State persistence
- Rate limiting
- Buffer management
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class StreamState(str, Enum):
    """States of a streaming session."""
    IDLE = "idle"
    STREAMING = "streaming"
    PAUSED = "paused"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class StreamChunk:
    """A chunk of streamed content."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    is_first: bool = False
    is_last: bool = False
    index: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "is_first": self.is_first,
            "is_last": self.is_last,
            "index": self.index,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class StreamSession:
    """A streaming session."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    state: StreamState = StreamState.IDLE
    chunks: List[StreamChunk] = field(default_factory=list)
    total_chunks: int = 0
    total_tokens: int = 0
    buffer: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    interrupted_at: Optional[datetime] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "state": self.state.value,
            "total_chunks": self.total_chunks,
            "total_tokens": self.total_tokens,
            "buffer": self.buffer,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "interrupted_at": self.interrupted_at.isoformat() if self.interrupted_at else None,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass
class StreamConfig:
    """Configuration for streaming."""
    chunk_size: int = 100  # characters per chunk
    buffer_size: int = 1000  # character buffer
    rate_limit: Optional[float] = None  # tokens per second
    enable_interrupt: bool = True
    auto_resume: bool = True
    timeout: float = 30.0


class StreamingService:
    """Token streaming with interrupt handling and resume capability.

    Manages streaming sessions, handles user interrupts, and
    provides state management for streaming operations.
    """

    def __init__(self):
        self._sessions: Dict[str, StreamSession] = {}
        self._request_sessions: Dict[str, str] = {}  # request_id -> session_id
        self._stream_handlers: Dict[str, Callable] = {}
        self._default_config = StreamConfig()
        self._active_interrupts: Dict[str, asyncio.Event] = {}

    def set_stream_handler(self, handler_id: str, handler: Callable) -> None:
        """Register a stream handler."""
        self._stream_handlers[handler_id] = handler
        logger.info("Registered stream handler: %s", handler_id)

    async def create_session(
        self,
        request_id: str,
        config: Optional[StreamConfig] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> StreamSession:
        """Create a new streaming session.

        Args:
            request_id: Request identifier
            config: Optional streaming configuration
            metadata: Additional metadata

        Returns:
            The created session
        """
        session = StreamSession(
            request_id=request_id,
            metadata=metadata or {},
        )

        self._sessions[session.id] = session
        self._request_sessions[request_id] = session.id

        logger.info("Created streaming session: %s for request: %s", session.id, request_id)
        return session

    def get_session(self, session_id: str) -> Optional[StreamSession]:
        """Get a session by ID."""
        return self._sessions.get(session_id)

    def get_session_by_request(self, request_id: str) -> Optional[StreamSession]:
        """Get a session by request ID."""
        session_id = self._request_sessions.get(request_id)
        if session_id:
            return self._sessions.get(session_id)
        return None

    async def stream(
        self,
        session_id: str,
        token_generator: AsyncIterator[str],
        config: Optional[StreamConfig] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream tokens from a generator.

        Args:
            session_id: Session ID
            token_generator: Async iterator yielding tokens
            config: Optional streaming configuration

        Yields:
            Stream chunks
        """
        config = config or self._default_config
        session = self._sessions.get(session_id)

        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.state = StreamState.STREAMING
        session.started_at = datetime.now(timezone.utc)

        # Create interrupt event
        interrupt_event = asyncio.Event()
        self._active_interrupts[session_id] = interrupt_event

        buffer = ""
        chunk_index = 0
        total_tokens = 0

        try:
            async for token in token_generator:
                # Check for interrupt
                if config.enable_interrupt and interrupt_event.is_set():
                    session.state = StreamState.INTERRUPTED
                    session.interrupted_at = datetime.now(timezone.utc)
                    logger.info("Stream interrupted: %s", session_id)
                    break

                # Add to buffer
                buffer += token
                total_tokens += 1

                # Yield chunk if buffer is large enough
                if len(buffer) >= config.chunk_size:
                    chunk = StreamChunk(
                        content=buffer[:config.chunk_size],
                        is_first=(chunk_index == 0),
                        index=chunk_index,
                    )
                    session.chunks.append(chunk)
                    session.total_chunks += 1
                    session.buffer = buffer[config.chunk_size:]
                    buffer = session.buffer

                    chunk_index += 1
                    yield chunk

                    # Rate limiting
                    if config.rate_limit:
                        await asyncio.sleep(1.0 / config.rate_limit)

            # Yield remaining buffer
            if buffer:
                chunk = StreamChunk(
                    content=buffer,
                    is_first=(chunk_index == 0),
                    is_last=True,
                    index=chunk_index,
                )
                session.chunks.append(chunk)
                session.total_chunks += 1
                session.buffer = ""
                yield chunk

            session.state = StreamState.COMPLETED
            session.completed_at = datetime.now(timezone.utc)
            session.total_tokens = total_tokens

            logger.info(
                "Stream completed: %s (%d chunks, %d tokens)",
                session_id,
                session.total_chunks,
                total_tokens,
            )

        except Exception as exc:
            session.state = StreamState.ERROR
            session.error = str(exc)
            logger.error("Stream error: %s - %s", session_id, exc)
            raise

        finally:
            # Clean up interrupt event
            if session_id in self._active_interrupts:
                del self._active_interrupts[session_id]

    async def interrupt(self, session_id: str) -> bool:
        """Interrupt a streaming session.

        Args:
            session_id: Session ID to interrupt

        Returns:
            True if interrupt was triggered
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.state != StreamState.STREAMING:
            return False

        interrupt_event = self._active_interrupts.get(session_id)
        if interrupt_event:
            interrupt_event.set()
            logger.info("Interrupt triggered for session: %s", session_id)
            return True

        return False

    async def resume(
        self,
        session_id: str,
        token_generator: AsyncIterator[str],
        config: Optional[StreamConfig] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Resume an interrupted streaming session.

        Args:
            session_id: Session ID to resume
            token_generator: New token generator
            config: Optional streaming configuration

        Yields:
            Stream chunks
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.state not in (StreamState.INTERRUPTED, StreamState.PAUSED):
            raise ValueError(f"Cannot resume session in state: {session.state.value}")

        logger.info("Resuming session: %s", session_id)

        # Update session state
        session.state = StreamState.STREAMING
        session.interrupted_at = None

        # Continue streaming
        async for chunk in self.stream(session_id, token_generator, config):
            yield chunk

    async def pause(self, session_id: str) -> bool:
        """Pause a streaming session.

        Args:
            session_id: Session ID to pause

        Returns:
            True if paused successfully
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        if session.state != StreamState.STREAMING:
            return False

        # Trigger interrupt to pause
        interrupted = await self.interrupt(session_id)
        if interrupted:
            session.state = StreamState.PAUSED
            logger.info("Paused session: %s", session_id)
            return True

        return False

    def get_streamed_content(self, session_id: str) -> str:
        """Get the complete streamed content for a session.

        Args:
            session_id: Session ID

        Returns:
            Complete content string
        """
        session = self._sessions.get(session_id)
        if not session:
            return ""

        content = ""
        for chunk in session.chunks:
            content += chunk.content
        content += session.buffer

        return content

    def get_session_progress(self, session_id: str) -> Dict[str, Any]:
        """Get progress information for a session.

        Args:
            session_id: Session ID

        Returns:
            Progress information
        """
        session = self._sessions.get(session_id)
        if not session:
            return {}

        return {
            "session_id": session_id,
            "state": session.state.value,
            "total_chunks": session.total_chunks,
            "total_tokens": session.total_tokens,
            "buffer_length": len(session.buffer),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "error": session.error,
        }

    async def delete_session(self, session_id: str) -> bool:
        """Delete a streaming session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        # Interrupt if streaming
        if session.state == StreamState.STREAMING:
            await self.interrupt(session_id)

        # Remove from indexes
        if session.request_id in self._request_sessions:
            del self._request_sessions[session.request_id]

        del self._sessions[session_id]

        logger.info("Deleted streaming session: %s", session_id)
        return True

    async def cleanup_old_sessions(self, max_age_hours: float = 24.0) -> int:
        """Clean up old sessions.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of sessions deleted
        """
        now = datetime.now(timezone.utc)
        max_age = timedelta(hours=max_age_hours)

        old_sessions = [
            sid for sid, session in self._sessions.items()
            if (now - session.created_at) > max_age
        ]

        for session_id in old_sessions:
            await self.delete_session(session_id)

        logger.info("Cleaned up %d old sessions", len(old_sessions))
        return len(old_sessions)

    def get_statistics(self) -> Dict[str, Any]:
        """Get streaming service statistics."""
        return {
            "total_sessions": len(self._sessions),
            "by_state": {
                state.value: len([s for s in self._sessions.values() if s.state == state])
                for state in StreamState
            },
            "total_chunks": sum(s.total_chunks for s in self._sessions.values()),
            "total_tokens": sum(s.total_tokens for s in self._sessions.values()),
            "active_interrupts": len(self._active_interrupts),
        }
