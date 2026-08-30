"""Ollama lifecycle manager for DASH.

Provides:
- Health checking (is Ollama reachable?)
- Auto-start (launch ollama serve if not running)
- Model verification (is the configured model available?)
- Status reporting (for UI display)

States: STARTING, CONNECTING, READY, DEGRADED, ERROR
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from enum import Enum
from typing import Optional

import httpx

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class OllamaState(str, Enum):
    STARTING = "starting"
    CONNECTING = "connecting"
    READY = "ready"
    DEGRADED = "degraded"  # Ollama running but model unavailable
    ERROR = "error"
    STOPPED = "stopped"


class OllamaManager:
    """Manages Ollama lifecycle for DASH."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "llama3.2:1b",
        auto_start: bool = True,
        health_check_interval: int = 30,
    ):
        self.base_url = base_url
        self.model = model
        self.auto_start = auto_start
        self.health_check_interval = health_check_interval
        self._state = OllamaState.STOPPED
        self._last_health_check = 0.0
        self._model_available = False
        self._process: Optional[subprocess.Popen] = None
        self._health_task: Optional[asyncio.Task] = None

    @property
    def state(self) -> OllamaState:
        return self._state

    @property
    def model_available(self) -> bool:
        return self._model_available

    def get_status(self) -> dict:
        return {
            "state": self._state.value,
            "base_url": self.base_url,
            "model": self.model,
            "model_available": self._model_available,
            "last_health_check": self._last_health_check,
        }

    async def check_health(self) -> bool:
        """Check if Ollama is reachable and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check Ollama is running
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    self._state = OllamaState.ERROR
                    return False

                self._last_health_check = time.time()

                # Check if configured model is available
                data = resp.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                self._model_available = any(
                    self.model in m for m in models
                )

                if self._model_available:
                    self._state = OllamaState.READY
                else:
                    self._state = OllamaState.DEGRADED
                    logger.warning(
                        "Ollama running but model '%s' not found. Available: %s",
                        self.model,
                        models,
                    )

                return self._model_available

        except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
            logger.debug("Ollama health check failed: %s", e)
            self._state = OllamaState.STOPPED
            return False

    async def start(self) -> bool:
        """Start Ollama if not running."""
        # First check if already running
        if await self.check_health():
            logger.info("Ollama already running and healthy")
            return True

        if not self.auto_start:
            self._state = OllamaState.ERROR
            logger.error("Ollama not running and auto_start is disabled")
            return False

        self._state = OllamaState.STARTING
        logger.info("Starting Ollama...")

        try:
            # Try to start ollama serve in background
            import sys
            if sys.platform == "win32":
                self._process = subprocess.Popen(
                    ["ollama", "serve"],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                self._process = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # Wait for Ollama to become healthy (max 30s)
            self._state = OllamaState.CONNECTING
            for i in range(30):
                await asyncio.sleep(1)
                if await self.check_health():
                    logger.info("Ollama started successfully (took %ds)", i + 1)
                    return True

            logger.error("Ollama failed to start within 30 seconds")
            self._state = OllamaState.ERROR
            return False

        except FileNotFoundError:
            logger.error("Ollama binary not found on PATH")
            self._state = OllamaState.ERROR
            return False
        except Exception as e:
            logger.exception("Failed to start Ollama: %s", e)
            self._state = OllamaState.ERROR
            return False

    async def ensure_ready(self) -> bool:
        """Ensure Ollama is running and the model is available. Start if needed."""
        if self._state == OllamaState.READY and self._model_available:
            # Still do periodic health checks
            if time.time() - self._last_health_check < self.health_check_interval:
                return True

        return await self.start()

    async def start_background_monitor(self) -> None:
        """Start background health monitoring task."""
        async def _monitor():
            while True:
                try:
                    await self.ensure_ready()
                except Exception as e:
                    logger.debug("Background Ollama monitor error: %s", e)
                await asyncio.sleep(self.health_check_interval)

        self._health_task = asyncio.create_task(_monitor())
        logger.info("Ollama background monitor started (interval=%ds)", self.health_check_interval)

    def stop(self) -> None:
        """Stop the background monitor."""
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
        self._state = OllamaState.STOPPED


# Singleton
_manager: Optional[OllamaManager] = None


def get_ollama_manager(
    base_url: str = "http://127.0.0.1:11434",
    model: str = "llama3.2:1b",
    auto_start: bool = True,
) -> OllamaManager:
    global _manager
    if _manager is None:
        _manager = OllamaManager(
            base_url=base_url,
            model=model,
            auto_start=auto_start,
        )
    return _manager
