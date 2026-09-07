"""CLI-based AI providers (Gemini CLI, Qwen CLI) - use subprocess to invoke CLI tools."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import time
from typing import Any, AsyncIterator

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderCapability,
    ProviderConfig,
    ProviderHealth,
)

logger = get_logger(__name__)


class CliProvider(AIProvider):
    """Provider that uses a CLI tool (e.g., gemini, qwen) via subprocess."""

    def __init__(
        self,
        name: str,
        cli_command: str,
        model: str = "",
        timeout: int = 120,
        capabilities: set[ProviderCapability] | None = None,
        extra_args: list[str] | None = None,
    ) -> None:
        self._name = name
        self._cli_command = cli_command
        caps = capabilities or {
            ProviderCapability.TEXT_COMPLETION,
            ProviderCapability.CHAT,
        }
        self._config = ProviderConfig(
            name=name,
            model=model,
            timeout_seconds=timeout,
            capabilities=caps,
            extra={"cli_command": cli_command, "extra_args": extra_args or []},
        )
        self._cancelled = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def config(self) -> ProviderConfig:
        return self._config

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self._cancelled = False
        prompt = self._build_prompt(request)
        args = [self._cli_command] + self.config.extra.get("extra_args", [])
        args.extend(["--prompt", prompt])

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self._config.timeout_seconds
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            return CompletionResponse(content=stdout.strip())
        except asyncio.TimeoutError:
            raise RuntimeError(f"{self._name} timed out after {self._config.timeout_seconds}s")
        except FileNotFoundError:
            raise RuntimeError(f"CLI not found: {self._cli_command}")
        except Exception as exc:
            raise RuntimeError(f"{self._name} failed: {exc}") from exc

    async def complete_streaming(self, request: CompletionRequest) -> AsyncIterator[str]:
        self._cancelled = False
        prompt = self._build_prompt(request)
        args = [self._cli_command] + self.config.extra.get("extra_args", [])
        args.extend(["--prompt", prompt])

        try:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Stream stdout line by line
            while True:
                if self._cancelled:
                    process.kill()
                    break
                line = await process.stdout.readline()
                if not line:
                    break
                token = line.decode("utf-8", errors="replace")
                if token.strip():
                    yield token
            await process.wait()
        except Exception as exc:
            raise RuntimeError(f"{self._name} streaming failed: {exc}") from exc

    async def check_health(self) -> ProviderHealth:
        start = time.monotonic()
        cli_path = shutil.which(self._cli_command)
        if cli_path is None:
            return ProviderHealth(healthy=False, error=f"CLI not found: {self._cli_command}")

        try:
            process = await asyncio.create_subprocess_exec(
                self._cli_command, "--help" if self._name != "ollama" else "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.wait(), timeout=10.0)
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(
                healthy=process.returncode == 0,
                latency_ms=round(latency, 1),
                model_loaded=True,
            )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProviderHealth(
                healthy=False,
                latency_ms=round(latency, 1),
                error=str(exc),
            )

    async def cancel(self) -> None:
        self._cancelled = True

    @staticmethod
    def _build_prompt(request: CompletionRequest) -> str:
        parts = []
        if request.system_prompt:
            parts.append(f"System: {request.system_prompt}")
        for msg in request.messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            parts.append(f"{role}: {content}")
        return "\n".join(parts)
