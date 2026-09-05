"""Proactive Agent — runs autonomously when the user is idle.

When DASH detects the user hasn't interacted for a while, it can:
- Monitor system health and fix issues
- Organize files
- Learn from past interactions
- Run scheduled maintenance
- Optimize system performance
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ProactiveAgent:
    """Runs autonomous tasks during idle periods."""

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._idle_threshold = 300.0  # 5 minutes
        self._last_activity = time.time()
        self._last_proactive_run = 0.0
        self._proactive_interval = 1800.0  # 30 minutes between proactive runs
        self._tasks_completed = 0

    def register_activity(self) -> None:
        """Call this whenever the user interacts with DASH."""
        self._last_activity = time.time()

    async def start(self) -> None:
        """Start the proactive monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("ProactiveAgent started (idle threshold: %ss)", self._idle_threshold)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    async def _loop(self) -> None:
        """Main monitoring loop — checks for idle periods and runs tasks."""
        while self._running:
            try:
                idle_time = time.time() - self._last_activity
                since_last_run = time.time() - self._last_proactive_run

                if idle_time > self._idle_threshold and since_last_run > self._proactive_interval:
                    await self._run_proactive_tasks()
                    self._last_proactive_run = time.time()

                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("ProactiveAgent loop error: %s", exc)
                await asyncio.sleep(60)

    async def _run_proactive_tasks(self) -> None:
        """Run a set of proactive improvement tasks."""
        logger.info("ProactiveAgent: running proactive tasks")

        tasks = [
            self._check_system_health(),
            self._optimize_memory(),
            self._check_disk_space(),
        ]

        for task_coro in tasks:
            try:
                await asyncio.wait_for(task_coro, timeout=30.0)
            except asyncio.TimeoutError:
                logger.debug("Proactive task timed out")
            except Exception as exc:
                logger.debug("Proactive task failed: %s", exc)

        self._tasks_completed += 1
        logger.info("ProactiveAgent: completed proactive cycle #%d", self._tasks_completed)

    async def _check_system_health(self) -> None:
        """Check CPU, RAM, disk and log warnings if critical."""
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent

            if cpu > 90:
                logger.warning("ProactiveAgent: HIGH CPU — %.1f%%", cpu)
            if ram > 90:
                logger.warning("ProactiveAgent: HIGH RAM — %.1f%%", ram)
            if disk > 90:
                logger.warning("ProactiveAgent: HIGH DISK — %.1f%%", disk)
        except Exception:
            pass

    async def _optimize_memory(self) -> None:
        """Ask the LLM if there are any memory optimizations to suggest."""
        try:
            from dash_backend.llm.service import build_chat_messages, collect_streamed_response
            import psutil

            ram = psutil.virtual_memory()
            top_procs = []
            for p in sorted(
                psutil.process_iter(["pid", "name", "memory_info"]),
                key=lambda x: x.info.get("memory_info", None) and x.info["memory_info"].rss or 0,
                reverse=True,
            )[:5]:
                name = p.info.get("name", "?")
                rss = (p.info.get("memory_info") or type("", (), {"rss": 0})()).rss
                top_procs.append(f"{name}: {rss // (1024*1024)}MB")

            messages = build_chat_messages(
                system_prompt="You are a system optimizer. Analyze the system state and suggest ONE specific optimization. Be concise.",
                user_message=(
                    f"RAM: {ram.percent}% used ({ram.used // (1024**3)}GB / {ram.total // (1024**3)}GB)\n"
                    f"Top memory consumers: {', '.join(top_procs)}\n"
                    f"Suggest ONE actionable optimization."
                ),
            )
            await asyncio.wait_for(collect_streamed_response(messages), timeout=15.0)
        except Exception:
            pass

    async def _check_disk_space(self) -> None:
        """Check disk space and suggest cleanup if needed."""
        try:
            import psutil
            disk = psutil.disk_usage("/")
            if disk.percent > 85:
                logger.warning(
                    "ProactiveAgent: Disk %.1f%% full — consider cleanup",
                    disk.percent,
                )
        except Exception:
            pass

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "idle_threshold": self._idle_threshold,
            "idle_for": round(time.time() - self._last_activity, 1),
            "tasks_completed": self._tasks_completed,
            "last_run": self._last_proactive_run,
        }


_proactive: ProactiveAgent | None = None


def get_proactive_agent() -> ProactiveAgent:
    global _proactive
    if _proactive is None:
        _proactive = ProactiveAgent()
    return _proactive
