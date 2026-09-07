"""Ollama provider manager with auto-start, health checks, and recovery.

This module handles:
- Automatic Ollama discovery on Windows
- Ollama startup management (no duplicate instances)
- Provider health monitoring
- Model availability verification
- Structured provider status reporting
- Automatic recovery from transient failures
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import AsyncIterator

import httpx

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ProviderStatus(str, Enum):
    """Provider health states."""
    CHECKING = "checking"
    STARTING = "starting"
    READY = "ready"
    MODEL_MISSING = "model_missing"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass
class ProviderHealth:
    """Structured provider health information."""
    status: ProviderStatus
    provider: str
    configured_model: str | None
    model_available: bool
    installed_models: list[str]
    error: str | None
    latency_ms: float | None
    message: str  # User-friendly message


class OllamaManager:
    """Manages Ollama lifecycle including discovery, startup, and health monitoring."""

    def __init__(self):
        self._ollama_process: subprocess.Popen | None = None
        self._current_status = ProviderStatus.CHECKING
        self._last_health_check: float = 0
        self._health_check_interval = 30.0  # seconds
        self._startup_timeout = 30.0  # seconds to wait for Ollama to start
        self._max_startup_retries = 3

    @property
    def status(self) -> ProviderStatus:
        """Current provider status."""
        return self._current_status

    def find_ollama_executable(self) -> str | None:
        """Discover Ollama executable on Windows.

        Checks:
        1. PATH environment variable
        2. Common Windows installation paths
        3. User-specific installation paths

        Returns:
            Path to ollama executable or None if not found.
        """
        if platform.system() != "Windows":
            logger.warning("Ollama auto-start only supported on Windows")
            return None

        # Check PATH first
        ollama_in_path = shutil.which("ollama.exe")
        if ollama_in_path:
            logger.info("Found Ollama in PATH: %s", ollama_in_path)
            return ollama_in_path

        # Check common installation paths
        common_paths = [
            r"C:\Users\{}\AppData\Local\Programs\Ollama\ollama.exe".format(os.getenv("USERNAME", "")),
            r"C:\Program Files\Ollama\ollama.exe",
            r"C:\Program Files (x86)\Ollama\ollama.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Ollama\ollama.exe"),
        ]

        for path in common_paths:
            if os.path.exists(path):
                logger.info("Found Ollama at: %s", path)
                return path

        logger.warning("Ollama executable not found in common locations")
        return None

    def is_ollama_running(self) -> bool:
        """Check if Ollama is already running by testing the API."""
        settings = get_settings()
        base_url = settings.ollama_base_url.rstrip("/")
        tags_url = f"{base_url}/api/tags"

        try:
            response = httpx.get(tags_url, timeout=2.0)
            if response.status_code == 200:
                logger.info("Ollama is already running at %s", base_url)
                return True
        except Exception:
            pass

        return False

    async def start_ollama(self, executable: str) -> bool:
        """Start Ollama as a background process on Windows.

        Args:
            executable: Path to ollama.exe

        Returns:
            True if started successfully, False otherwise.
        """
        if platform.system() != "Windows":
            logger.warning("Ollama auto-start only supported on Windows")
            return False

        try:
            # Start Ollama with CREATE_NO_WINDOW to avoid visible terminal
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            self._ollama_process = subprocess.Popen(
                [executable, "serve"],
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            logger.info("Started Ollama process (PID: %d)", self._ollama_process.pid)
            return True

        except Exception as exc:
            logger.error("Failed to start Ollama: %s", exc)
            return False

    async def wait_for_ollama_api(self, timeout: float = 30.0) -> bool:
        """Wait for Ollama API to become available.

        Args:
            timeout: Maximum seconds to wait

        Returns:
            True if API becomes available, False otherwise.
        """
        settings = get_settings()
        base_url = settings.ollama_base_url.rstrip("/")
        tags_url = f"{base_url}/api/tags"

        start_time = asyncio.get_event_loop().time()
        check_interval = 1.0

        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                response = await asyncio.to_thread(httpx.get, tags_url, timeout=2.0)
                if response.status_code == 200:
                    logger.info("Ollama API is ready")
                    return True
            except Exception:
                pass

            await asyncio.sleep(check_interval)

        logger.warning("Ollama API did not become available within timeout")
        return False

    async def get_installed_models(self) -> list[str]:
        """Query Ollama for installed models.

        Returns:
            List of model names.
        """
        settings = get_settings()
        base_url = settings.ollama_base_url.rstrip("/")
        tags_url = f"{base_url}/api/tags"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(tags_url)
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("models", [])
                    return [m.get("name", "") for m in models if m.get("name")]
        except Exception as exc:
            logger.warning("Failed to query Ollama models: %s", exc)

        return []

    def get_configured_model(self) -> str | None:
        """Get the configured Ollama model from settings.

        Returns:
            Model name or None.
        """
        settings = get_settings()
        if settings.ai_model:
            return settings.ai_model
        if settings.ollama_model:
            return settings.ollama_model
        return None

    def is_model_available(self, model: str, installed_models: list[str]) -> bool:
        """Check if a model is in the installed models list.

        Args:
            model: Model name to check
            installed_models: List of installed model names

        Returns:
            True if model is available.
        """
        if not model:
            return False

        # Check with and without :latest suffix
        return any(
            model == m or
            model == m.replace(":latest", "") or
            f"{model}:latest" == m
            for m in installed_models
        )

    async def check_health(self) -> ProviderHealth:
        """Perform comprehensive provider health check.

        Returns:
            ProviderHealth with current status and details.
        """
        settings = get_settings()
        provider = settings.ai_provider.lower()
        base_url = settings.ollama_base_url.rstrip("/")

        self._current_status = ProviderStatus.CHECKING

        result = ProviderHealth(
            status=ProviderStatus.CHECKING,
            provider=provider,
            configured_model=None,
            model_available=False,
            installed_models=[],
            error=None,
            latency_ms=None,
            message="Checking AI provider...",
        )

        try:
            if provider == "ollama":
                # Check if Ollama is running
                if not self.is_ollama_running():
                    logger.info("Ollama not running, attempting to start")
                    self._current_status = ProviderStatus.STARTING
                    result.status = ProviderStatus.STARTING
                    result.message = "Starting Ollama..."

                    # Try to find and start Ollama
                    executable = self.find_ollama_executable()
                    if not executable:
                        result.status = ProviderStatus.UNAVAILABLE
                        result.error = "Ollama executable not found"
                        result.message = "AI engine not installed. Please install Ollama."
                        self._current_status = ProviderStatus.UNAVAILABLE
                        return result

                    # Start Ollama
                    if not await self.start_ollama(executable):
                        result.status = ProviderStatus.ERROR
                        result.error = "Failed to start Ollama"
                        result.message = "Could not start AI engine."
                        self._current_status = ProviderStatus.ERROR
                        return result

                    # Wait for API
                    if not await self.wait_for_ollama_api(self._startup_timeout):
                        result.status = ProviderStatus.ERROR
                        result.error = "Ollama API did not become available"
                        result.message = "AI engine failed to start."
                        self._current_status = ProviderStatus.ERROR
                        return result

                # Ollama is running, check models
                start_time = asyncio.get_event_loop().time()
                installed_models = await self.get_installed_models()
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                result.installed_models = installed_models
                result.latency_ms = latency_ms

                # Get configured model
                configured_model = self.get_configured_model()
                result.configured_model = configured_model

                # Check model availability with fallback logic
                selected_model = configured_model
                if configured_model and self.is_model_available(configured_model, installed_models):
                    result.status = ProviderStatus.READY
                    result.model_available = True
                    result.message = "AI engine ready."
                    self._current_status = ProviderStatus.READY
                elif configured_model:
                    # Configured model not available, try fallback models
                    fallback_models = ["llama3.2:3b", "qwen2.5-coder", "llama3.1:8b", "llama3:8b"]
                    for fallback in fallback_models:
                        if self.is_model_available(fallback, installed_models):
                            selected_model = fallback
                            result.configured_model = fallback
                            result.status = ProviderStatus.READY
                            result.model_available = True
                            result.message = f"AI engine ready using fallback model '{fallback}'."
                            self._current_status = ProviderStatus.READY
                            logger.info("Using fallback model '%s' instead of configured '%s'", fallback, configured_model)
                            break
                    
                    if result.status != ProviderStatus.READY:
                        result.status = ProviderStatus.MODEL_MISSING
                        result.model_available = False
                        result.error = f"Model '{configured_model}' not installed and no fallback available"
                        result.message = f"AI model '{configured_model}' is not installed. Please install it or another compatible model."
                        self._current_status = ProviderStatus.MODEL_MISSING
                else:
                    # No configured model, select first available
                    if installed_models:
                        selected_model = installed_models[0]
                        result.configured_model = selected_model
                        result.status = ProviderStatus.READY
                        result.model_available = True
                        result.message = f"AI engine ready using '{selected_model}'."
                        self._current_status = ProviderStatus.READY
                    else:
                        result.status = ProviderStatus.MODEL_MISSING
                        result.model_available = False
                        result.error = "No models installed"
                        result.message = "No AI models are installed. Please install Ollama and download a model."
                        self._current_status = ProviderStatus.MODEL_MISSING

            else:
                # OpenAI or other provider
                result.status = ProviderStatus.UNAVAILABLE
                result.message = f"Provider '{provider}' not managed by auto-start."
                self._current_status = ProviderStatus.UNAVAILABLE

        except asyncio.TimeoutError:
            result.status = ProviderStatus.ERROR
            result.error = "Health check timed out"
            result.message = "AI engine check timed out."
            self._current_status = ProviderStatus.ERROR
        except Exception as exc:
            result.status = ProviderStatus.ERROR
            result.error = str(exc)
            result.message = "AI engine check failed."
            self._current_status = ProviderStatus.ERROR
            logger.exception("Provider health check failed")

        return result

    async def ensure_provider_ready(self) -> ProviderHealth:
        """Ensure the provider is ready, starting it if necessary.

        This is the main entry point for startup health checks.
        Includes automatic recovery from transient failures.

        Returns:
            ProviderHealth with current status.
        """
        # Rate limit health checks
        now = asyncio.get_event_loop().time()
        if now - self._last_health_check < self._health_check_interval:
            # Return cached status if recent check exists
            return await self.check_health()

        self._last_health_check = now

        # Perform health check with recovery logic
        max_recovery_attempts = 2
        recovery_delay = 2.0

        for attempt in range(max_recovery_attempts + 1):
            health = await self.check_health()

            # If ready or permanently unavailable, return immediately
            if health.status in (ProviderStatus.READY, ProviderStatus.MODEL_MISSING, ProviderStatus.UNAVAILABLE):
                return health

            # If error, attempt recovery
            if health.status == ProviderStatus.ERROR and attempt < max_recovery_attempts:
                logger.info("Attempting provider recovery (attempt %d/%d)", attempt + 1, max_recovery_attempts)
                await asyncio.sleep(recovery_delay)
                recovery_delay *= 2  # Exponential backoff
                continue

            return health

        return health

    def stop_ollama(self) -> None:
        """Stop the Ollama process if we started it."""
        if self._ollama_process:
            try:
                self._ollama_process.terminate()
                self._ollama_process.wait(timeout=5)
                logger.info("Stopped Ollama process")
            except Exception as exc:
                logger.warning("Failed to stop Ollama process: %s", exc)
            finally:
                self._ollama_process = None


# Global singleton instance
_ollama_manager: OllamaManager | None = None


def get_ollama_manager() -> OllamaManager:
    """Get the global Ollama manager singleton."""
    global _ollama_manager
    if _ollama_manager is None:
        _ollama_manager = OllamaManager()
    return _ollama_manager


async def get_provider_health() -> ProviderHealth:
    """Convenience function to get current provider health."""
    manager = get_ollama_manager()
    return await manager.ensure_provider_ready()


def get_provider_status() -> ProviderStatus:
    """Convenience function to get current provider status."""
    manager = get_ollama_manager()
    return manager.status
