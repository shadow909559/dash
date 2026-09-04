"""Autonomous Brain — the central orchestrator that makes DASH self-directing.

This is the JARVIS layer. It connects:
  - System Monitor  →  alerts trigger autonomous responses
  - Idle Detector   →  idle periods trigger proactive improvements
  - Chat Messages   →  natural language triggers goal execution
  - Agent Core      →  executes multi-step plans via tools
  - Memory          →  remembers what worked and adapts

The brain doesn't execute anything itself. It observes, decides, and
delegates to the agent core which does the actual work through tools.

Boot sequence:
  1. System health check (CPU, RAM, disk, processes)
  2. Report status to connected clients
  3. Start monitoring loops
  4. Wait for events or user interaction
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ── Status constants ──────────────────────────────────────────────────────

BOOT_GREETING = (
    "Good {time_of_day}, sir. All systems are operational. "
    "{cpu_status} {ram_status} {disk_status}"
)

ALERT_RESPONSES = {
    "cpu": "CPU usage has exceeded {value}%. I'll investigate what's consuming resources.",
    "memory": "Memory usage is at {value}%. Let me identify the top consumers.",
    "disk": "Disk usage on {mount} is at {value}%. I'll find what's taking up space.",
    "battery": "Battery is at {value}%. Consider connecting to power.",
}


class AutonomousBrain:
    """The JARVIS orchestrator.

    Observes the system through monitors, decides what action to take,
    and delegates execution to the agent core.  Runs continuously in
    the background, waking up on events or at scheduled intervals.
    """

    def __init__(self):
        self._running = False
        self._task: asyncio.Task | None = None
        self._boot_complete = False
        self._last_status_report: dict[str, Any] = {}
        self._alert_cooldown: dict[str, float] = {}  # alert_type -> last_handled
        self._cooldown_seconds = 300.0  # don't re-handle same alert within 5 min
        self._conversations: list[dict[str, Any]] = []  # chat history for context
        self._max_conversations = 50
        self._last_memory_maintenance: float = 0.0
        self._memory_maintenance_interval: float = 3600.0  # run every hour

    async def start(self) -> None:
        """Start the brain — run boot sequence then enter monitoring loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("AutonomousBrain started")

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()

    # ── Main Loop ──────────────────────────────────────────────────────

    async def _run(self) -> None:
        """Main brain loop: boot → monitor → react."""
        try:
            # Boot sequence
            await self._boot()
            self._boot_complete = True

            # Monitoring loop — check every 60s
            while self._running:
                await asyncio.sleep(60)
                if not self._running:
                    break
                await self._monitor_cycle()

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.exception("Brain loop failed: %s", exc)

    # ── Boot Sequence ──────────────────────────────────────────────────

    async def _boot(self) -> None:
        """JARVIS boot: check system health, report status, wire events."""
        logger.info("Brain: boot sequence starting")
        t0 = time.time()

        # 1. System health check
        status = await self._check_system_health()
        self._last_status_report = status

        # 2. Wire system monitor alerts
        try:
            from dash_backend.autonomous.system_monitor_agent import get_system_monitor_agent
            monitor = get_system_monitor_agent()
            monitor.on_alert(self._handle_alert)
            logger.info("Brain: wired to system monitor alerts")
        except Exception as exc:
            logger.debug("Could not wire system monitor: %s", exc)

        # 3. Wire idle detector
        try:
            from dash_backend.autonomous.idle_detector import get_idle_detector
            detector = get_idle_detector()
            detector.on_idle(self._handle_idle)
            logger.info("Brain: wired to idle detector")
        except Exception as exc:
            logger.debug("Could not wire idle detector: %s", exc)

        # 4. Load past experiences from database
        try:
            from dash_backend.autonomous.experience import get_experience_cache
            exp_cache = get_experience_cache()
            loaded = await exp_cache.load_from_db()
            if loaded > 0:
                logger.info("Brain: loaded %d past experiences from database", loaded)
        except Exception as exc:
            logger.debug("Could not load experiences: %s", exc)

        # 5. Schedule daily health report at 8am
        try:
            from dash_backend.services.system.scheduler import get_system_scheduler
            from dash_backend.autonomous.daily_report import generate_daily_report, _format_report_text

            async def _run_daily_report() -> None:
                report = await generate_daily_report()
                text = _format_report_text(report)
                await self._notify("daily.report", {"report": report, "text": text})
                logger.info("Daily report generated and broadcast")

            scheduler = get_system_scheduler()
            scheduler.add_daily_task("Daily Health Report", _run_daily_report, "08:00")
            logger.info("Brain: scheduled daily health report at 08:00")
        except Exception as exc:
            logger.debug("Could not schedule daily report: %s", exc)

        # 6. Register recurring maintenance tasks
        try:
            from dash_backend.autonomous.recurring_tasks import register_recurring_tasks
            register_recurring_tasks()
            logger.info("Brain: registered recurring maintenance tasks")
        except Exception as exc:
            logger.debug("Could not register recurring tasks: %s", exc)

        # 7. Report boot status to connected clients
        await self._notify_boot_status(status)

        elapsed = time.time() - t0
        logger.info("Brain: boot complete in %.1fs", elapsed)

    # ── System Health Check ────────────────────────────────────────────

    async def _check_system_health(self) -> dict[str, Any]:
        """Comprehensive system health check."""
        health: dict[str, Any] = {"timestamp": time.time(), "alerts": []}

        try:
            import psutil

            # CPU
            cpu = psutil.cpu_percent(interval=1)
            health["cpu_percent"] = cpu
            health["cpu_status"] = "CPU nominal" if cpu < 80 else f"CPU elevated at {cpu}%"
            if cpu > 90:
                health["alerts"].append({"type": "cpu", "value": cpu, "severity": "high"})

            # Memory
            mem = psutil.virtual_memory()
            health["ram_percent"] = mem.percent
            health["ram_used_gb"] = round(mem.used / (1024**3), 1)
            health["ram_total_gb"] = round(mem.total / (1024**3), 1)
            health["ram_status"] = "Memory nominal" if mem.percent < 80 else f"Memory at {mem.percent}%"
            if mem.percent > 90:
                health["alerts"].append({"type": "memory", "value": mem.percent, "severity": "high"})

            # Disk
            disk = psutil.disk_usage("C:\\")
            health["disk_percent"] = disk.percent
            health["disk_free_gb"] = round(disk.free / (1024**3), 1)
            health["disk_status"] = "Storage nominal" if disk.percent < 85 else f"Storage at {disk.percent}%"
            if disk.percent > 90:
                health["alerts"].append({"type": "disk", "value": disk.percent, "mount": "C:\\", "severity": "high"})

            # Top processes
            procs = []
            for p in sorted(
                psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]),
                key=lambda x: (x.info.get("memory_info") or type("", (), {"rss": 0})()).rss,
                reverse=True,
            )[:5]:
                name = p.info.get("name", "?")
                rss = (p.info.get("memory_info") or type("", (), {"rss": 0})()).rss
                procs.append({"name": name, "memory_mb": round(rss / (1024**2), 1)})
            health["top_processes"] = procs

        except Exception as exc:
            health["error"] = str(exc)
            health["cpu_status"] = "System metrics unavailable"
            health["ram_status"] = ""
            health["disk_status"] = ""

        return health

    # ── Alert Handling ─────────────────────────────────────────────────

    def _handle_alert(self, alert: dict[str, Any]) -> None:
        """Called by system monitor when threshold exceeded."""
        alert_type = alert.get("type", "unknown")

        # Cooldown — don't re-handle same alert type within 5 min
        last = self._alert_cooldown.get(alert_type, 0)
        if time.time() - last < self._cooldown_seconds:
            return
        self._alert_cooldown[alert_type] = time.time()

        logger.info("Brain: alert received — %s", alert_type)
        # Schedule autonomous response (fire and forget)
        asyncio.create_task(self._respond_to_alert(alert))

    async def _respond_to_alert(self, alert: dict[str, Any]) -> None:
        """Create an autonomous goal to investigate and fix the alert."""
        alert_type = alert.get("type", "unknown")
        value = alert.get("value", 0)

        description = ALERT_RESPONSES.get(alert_type, f"System alert: {alert_type} at {value}")
        description = description.format(**alert)

        try:
            from dash_backend.autonomous.agent_core import get_agent_core
            core = get_agent_core()
            goal = await core.run_goal(
                description=f"Investigate and resolve: {description}",
                context={"source": "system_alert", "alert": alert},
                max_iterations=5,
                timeout=120.0,
            )
            logger.info("Brain: created goal %s for alert %s", goal.id[:12], alert_type)
        except Exception as exc:
            logger.warning("Brain: failed to create alert response goal: %s", exc)

    # ── Idle Handling ──────────────────────────────────────────────────

    def _handle_idle(self, idle_seconds: float) -> None:
        """Called by idle detector when user has been idle."""
        logger.info("Brain: user idle for %.0fs, considering proactive work", idle_seconds)
        asyncio.create_task(self._run_proactive_work())

    async def _run_proactive_work(self) -> None:
        """Pick the most impactful proactive task and run it."""
        try:
            import psutil
            # Check what needs attention
            disk = psutil.disk_usage("C:\\")
            mem = psutil.virtual_memory()

            # Prioritize: disk cleanup > memory optimization > general health
            if disk.percent > 80:
                desc = "Find and suggest large or duplicate files that can be cleaned up"
            elif mem.percent > 75:
                desc = "Identify memory-heavy processes and suggest optimizations"
            else:
                desc = "Run a system health check and report any anomalies"

            from dash_backend.autonomous.agent_core import get_agent_core
            core = get_agent_core()
            await core.run_goal(
                description=desc,
                context={"source": "idle_proactive", "idle_seconds": 300},
                max_iterations=3,
                timeout=90.0,
            )
        except Exception as exc:
            logger.debug("Brain: proactive work failed: %s", exc)

    # ── Chat Integration ───────────────────────────────────────────────

    async def handle_chat(self, message: str, user_id: str = "user", voice_mode: bool = False, agent_mode: str = "general") -> str:
        """Process a chat message through the autonomous brain.

        If the message is a complex task, create a goal and let the agent
        execute it.  If it's a simple question, answer directly via LLM.
        When voice_mode=True, responses are shorter and spoken-friendly.
        agent_mode selects the personality: general, coder, planner, research, executor.
        Returns the response text.
        """
        # Store in conversation history
        self._conversations.append({
            "role": "user",
            "content": message,
            "timestamp": time.time(),
        })
        if len(self._conversations) > self._max_conversations:
            self._conversations = self._conversations[-self._max_conversations:]

        from dash_backend.autonomous.planner import is_complex_goal

        if is_complex_goal(message):
            # Complex task — create an autonomous goal
            try:
                from dash_backend.autonomous.agent_core import get_agent_core
                core = get_agent_core()
                goal = await core.run_goal(
                    description=message,
                    context={"source": "chat", "user_id": user_id},
                    max_iterations=10,
                    timeout=180.0,
                )
                response = (
                    f"I've started working on that. "
                    f"Goal {goal.id[:8]} is now running autonomously. "
                    f"I'll let you know when it's complete."
                )
            except Exception as exc:
                response = f"I encountered an issue starting that task: {exc}"
        else:
            # Simple question — answer via LLM
            try:
                from dash_backend.llm.service import build_chat_messages, collect_streamed_response
                from dash_backend.llm.fine_tuner import get_fine_tuning_manager
                context = self._build_context()
                # Retrieve relevant memories for context
                memory_context = await self._retrieve_memories(message, user_id)
                if memory_context:
                    context = f"{context}\n\n{memory_context}"
                # RAG: search Obsidian vault and code repos for relevant context
                rag_context = ""
                try:
                    ftm = get_fine_tuning_manager()
                    await ftm.rag_engine.initialize()
                    rag_results = await ftm.rag_engine.search(message, top_k=3)
                    if rag_results:
                        rag_parts = []
                        for r in rag_results:
                            rag_parts.append(f"[{r.source.split(chr(92))[-1]}] {r.content[:300]}")
                        rag_context = "\n\nRELEVANT DOCUMENTS:\n" + "\n".join(rag_parts)
                except Exception:
                    pass  # RAG not initialized yet, skip silently
                # Get agent-mode-specific system prompt
                spoken_rules = (
                    " RULES FOR VOICE MODE: Keep replies under 2 sentences. "
                    "No formatting, no lists, no markdown. Just speak naturally."
                    if voice_mode else ""
                )
                try:
                    ftm = get_fine_tuning_manager()
                    system_prompt = ftm.prompt_engine.get_system_prompt(agent_mode)
                except Exception:
                    system_prompt = (
                        "You are DASH, an AI assistant similar to JARVIS. "
                        "You are running on the user's Windows computer. "
                        "Be concise, helpful, and slightly formal."
                    )
                messages = build_chat_messages(
                    system_prompt=(
                        f"{system_prompt}"
                        f"{spoken_rules}"
                        f"\n\nSYSTEM STATUS:\n{context}"
                        f"{rag_context}"
                    ),
                    user_message=message,
                )
                response = await asyncio.wait_for(
                    collect_streamed_response(messages),
                    timeout=30.0,
                )
            except asyncio.TimeoutError:
                response = "I'm thinking about that, but the response is taking longer than expected."
            except Exception as exc:
                response = f"I encountered an issue: {exc}"

        # Store response
        self._conversations.append({
            "role": "assistant",
            "content": response,
            "timestamp": time.time(),
        })

        return response

    def _build_context(self) -> str:
        """Build a context string from current system state."""
        parts = []
        if self._last_status_report:
            r = self._last_status_report
            parts.append(f"CPU: {r.get('cpu_percent', '?')}%")
            parts.append(f"RAM: {r.get('ram_percent', '?')}% ({r.get('ram_used_gb', '?')}/{r.get('ram_total_gb', '?')} GB)")
            parts.append(f"Disk: {r.get('disk_percent', '?')}% ({r.get('disk_free_gb', '?')} GB free)")
        return "\n".join(parts) if parts else "System status unknown"

    async def _retrieve_memories(self, query: str, user_id: str = "user") -> str:
        """Retrieve relevant long-term memories for context injection."""
        try:
            from dash_backend.db.session import AsyncSessionLocal
            from dash_backend.intelligence.memory_service import MemoryService

            svc = MemoryService()
            async with AsyncSessionLocal() as session:
                # Try to get user ID from user_id string
                import uuid
                try:
                    uid = uuid.UUID(user_id)
                except (ValueError, AttributeError):
                    uid = None

                if uid:
                    memories, _ = await svc.get_user_memories(
                        session, uid, limit=5, memory_type="fact"
                    )
                else:
                    memories = []

                if memories:
                    lines = [f"- {m.content[:100]}" for m in memories[:5]]
                    return "PAST MEMORIES:\n" + "\n".join(lines)
        except Exception as exc:
            logger.debug("Memory retrieval failed: %s", exc)
        return ""

    async def _store_memory(self, content: str, user_id: str = "user",
                            memory_type: str = "fact", importance: float = 0.5) -> None:
        """Store a memory for long-term recall."""
        try:
            from dash_backend.db.session import AsyncSessionLocal
            from dash_backend.intelligence.memory_service import MemoryService

            svc = MemoryService()
            async with AsyncSessionLocal() as session:
                import uuid
                try:
                    uid = uuid.UUID(user_id)
                except (ValueError, AttributeError):
                    return

                await svc.store_long_term(
                    session, uid, content,
                    memory_type=memory_type,
                    importance=importance,
                )
        except Exception as exc:
            logger.debug("Memory storage failed: %s", exc)

    # ── Notification ───────────────────────────────────────────────────

    async def _notify_boot_status(self, status: dict[str, Any]) -> None:
        """Send boot status to all connected WebSocket clients."""
        try:
            from dash_backend.autonomous.agent_core import get_agent_core
            core = get_agent_core()
            await core._notify("brain.boot", {
                "status": "online",
                "cpu": status.get("cpu_percent", 0),
                "ram": status.get("ram_percent", 0),
                "disk": status.get("disk_percent", 0),
                "alerts": status.get("alerts", []),
            })
        except Exception:
            pass

    # ── Monitoring Cycle ───────────────────────────────────────────────

    async def _monitor_cycle(self) -> None:
        """Periodic check — refresh system health, detect anomalies, heal services."""
        try:
            status = await self._check_system_health()
            self._last_status_report = status

            # If there are critical alerts, handle them
            for alert in status.get("alerts", []):
                self._handle_alert(alert)

            # Self-healing: check if core services are alive
            await self._check_services()

            # Memory maintenance (runs hourly, not every cycle)
            now = time.time()
            if now - self._last_memory_maintenance >= self._memory_maintenance_interval:
                self._last_memory_maintenance = now
                await self._memory_maintenance()
        except Exception as exc:
            logger.debug("Monitor cycle error: %s", exc)

    async def _check_services(self) -> None:
        """Check if backend, Ollama, and tunnel are alive. Restart if dead."""
        import asyncio.subprocess as Subprocess

        services = [
            {"name": "Ollama", "check": self._check_ollama, "restart": self._restart_ollama},
            {"name": "Backend", "check": self._check_backend, "restart": self._restart_backend},
        ]

        for svc in services:
            try:
                alive = await svc["check"]()
                if not alive:
                    logger.warning("Brain: %s is down, restarting...", svc["name"])
                    await svc["restart"]()
                    # Verify it came back
                    await asyncio.sleep(5)
                    if await svc["check"]():
                        logger.info("Brain: %s restarted successfully", svc["name"])
                    else:
                        logger.error("Brain: %s restart failed", svc["name"])
            except Exception as exc:
                logger.debug("Service check error (%s): %s", svc["name"], exc)

    async def _check_ollama(self) -> bool:
        """Check if Ollama is responding on port 11434."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection("127.0.0.1", 11434),
                timeout=3.0,
            )
            writer.close()
            await writer.wait_closed()
            return True
        except Exception:
            return False

    async def _check_backend(self) -> bool:
        """Check if the backend health endpoint responds."""
        try:
            import urllib.request
            req = urllib.request.Request("http://127.0.0.1:8000/health")
            resp = await asyncio.to_thread(urllib.request.urlopen, req, timeout=3)
            return resp.status == 200
        except Exception:
            return False

    async def _restart_ollama(self) -> None:
        """Restart Ollama service."""
        import subprocess
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            )
        except Exception as exc:
            logger.error("Failed to restart Ollama: %s", exc)

    async def _restart_backend(self) -> None:
        """Restart the backend via the scheduled task."""
        import subprocess
        try:
            subprocess.run(
                ["schtasks", "/Run", "/TN", "DASH-Backend"],
                capture_output=True, timeout=10,
            )
        except Exception as exc:
            logger.error("Failed to restart backend: %s", exc)

    # ── Memory Maintenance ────────────────────────────────────────────

    async def _memory_maintenance(self) -> None:
        """Hourly memory maintenance: prune expired memories, consolidate short-term."""
        try:
            from dash_backend.intelligence.memory_service import MemoryService
            svc = MemoryService()

            # 1. Clean up expired memories
            expired = await svc.cleanup_expired_memories()
            if expired > 0:
                logger.info("Brain: pruned %d expired memories", expired)

            # 2. Consolidate short-term memories that exceed threshold
            # (This runs per-conversation; we trigger for active conversations)
            for conv_id in list(svc._short_term_memory.keys()):
                stm = svc._short_term_memory.get(conv_id)
                if stm and len(stm.messages) >= svc._consolidation_threshold:
                    await svc._consolidate_memory(conv_id)
                    logger.debug("Brain: consolidated memory for conversation %s", conv_id)

            # 3. Report memory stats
            total = len(svc._long_term_memory)
            if total > 0:
                logger.info("Brain: memory maintenance complete — %d long-term memories", total)
        except Exception as exc:
            logger.debug("Memory maintenance error: %s", exc)

    # ── Status ─────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "boot_complete": self._boot_complete,
            "last_status": self._last_status_report,
            "conversations": len(self._conversations),
        }


_brain: AutonomousBrain | None = None


def get_brain() -> AutonomousBrain:
    global _brain
    if _brain is None:
        _brain = AutonomousBrain()
    return _brain
