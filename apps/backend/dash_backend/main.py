"""FastAPI application entry point.

Creates and configures the DASH AI OS backend with all routers,
middleware, lifespan events, and startup/shutdown hooks.

Integrates all core intelligence systems:
- Event Bus for publish/subscribe communication
- System Services for background scheduling/monitoring
- Performance Optimization for latency targets
- Enhanced Sync for desktop/mobile
- Plugin Manager for plugin lifecycle
- Autonomous Agent for proactive operations
- Memory Engine with advanced retrieval
"""

from __future__ import annotations

from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dash_backend.config import get_settings
from dash_backend.logging_config import setup_logging, get_logger
from dash_backend.api.router import api_router
from dash_backend.automation.scheduler import get_scheduler
from dash_backend.skills.register import register_skills
from dash_backend.tools.register_desktop import register_desktop_tools
from dash_backend.services.permission_manager import get_permission_manager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events for the application.
    Integrates all Phase 3 AI OS systems on boot.
    """
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting DASH AI OS backend (env=%s, debug=%s)", settings.env, settings.debug)

    # ── Database migrations (Alembic) ────────────────────────
    # Run pending migrations before any service touches the database.
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        import pathlib

        alembic_ini = pathlib.Path(__file__).resolve().parent.parent / "alembic.ini"
        if alembic_ini.exists():
            alembic_cfg = AlembicConfig(str(alembic_ini))
            # Point Alembic at the same database URL the app uses.
            alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
            # Retry: two DASH processes booting together (logon task + manual
            # start) can contend on SQLite even with busy_timeout, and a
            # failed migration previously left the app running against a
            # half-migrated schema. 3 attempts × short backoff.
            for attempt in range(1, 4):
                try:
                    alembic_command.upgrade(alembic_cfg, "head")
                    logger.info("Database migrations applied (alembic upgrade head)")
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    logger.warning(
                        "Boot migration attempt %d failed; retrying", attempt
                    )
                    import time
                    time.sleep(2 * attempt)
        else:
            logger.warning("alembic.ini not found — skipping auto-migration")
    except Exception:
        logger.exception("Alembic migration failed at startup")

    supabase_sync_task = None
    executive_worker_task = None
    if settings.supabase_sync_enabled:
        try:
            from dash_backend.sync.supabase_outbox_worker import get_supabase_outbox_worker

            supabase_sync_task = asyncio.create_task(get_supabase_outbox_worker().run())
            logger.info("Optional Supabase outbox worker started")
        except Exception:
            logger.exception("Failed to start optional Supabase outbox worker")

    # Establish the persistent local device identity (created on first run).
    try:
        from dash_backend.security.local_identity import get_identity

        identity = get_identity()
        logger.info(
            "DASH device identity ready install_id=%s token_fingerprint=%s",
            identity.install_id,
            identity.token_fingerprint,
        )
    except Exception:
        logger.exception("Failed to establish DASH device identity")

    # Eagerly register skills and tools
    register_skills()
    register_desktop_tools()

    # Initialize permission manager
    permission_manager = get_permission_manager()
    logger.info("Permission manager initialized")

    # The durable executive queue needs an active worker. It is started once
    # per DASH Core lifespan and cancelled during shutdown below.
    try:
        from dash_backend.executive.service import worker_loop

        executive_worker_task = asyncio.create_task(worker_loop())
        logger.info("Executive worker started")
    except Exception:
        logger.exception("Failed to start executive worker")

    # Ollama model warm-up (#136): load weights into memory in the background
    # so the FIRST user interaction after boot pays ~1 s, not ~21 s.
    try:
        from dash_backend.llm.warmup import start_model_warmup

        start_model_warmup()
        logger.info("LLM model warm-up scheduled")
    except Exception:
        logger.exception("Failed to schedule LLM warm-up")

    # Start automation scheduler
    scheduler = None
    try:
        scheduler = get_scheduler()
        scheduler.start()
    except Exception:
        logger.exception("Failed to start automation scheduler")

    # Proactive assistant loop (decisions.md #94): meeting reminders,
    # overdue actions, stale approvals — bounded, deduped, config-gated
    # (DASH_ASSISTANT_PROACTIVE=0 disables). Non-critical.
    try:
        import os as _os
        from pathlib import Path as _Path
        from dash_backend.assistant import proactive as _proactive
        from dash_backend.assistant.crm_store import get_crm_store

        _proactive.configure_state_dir(
            _Path(_os.getenv("DASH_CRM_DIR", str(_Path.home() / ".dash" / "crm"))))
        _assistant_notifier = None
        try:
            from dash_backend.services.notifications import NotificationService
            _assistant_notifier = NotificationService()
        except Exception:
            logger.info("proactive loop running without desktop notifier")
        _proactive.start_proactive_loop(
            get_crm_store(), orchestrator=None, notifier=_assistant_notifier)
    except Exception:
        logger.exception("Failed to start proactive assistant loop")

    # Start workflow trigger scheduler: fires workflows whose persisted
    # cron schedule is due (decisions.md #53). Non-critical: a failure to
    # start logs and continues — manual runs still work.
    try:
        from dash_backend.services.workflow_builder import get_workflow_trigger_scheduler
        get_workflow_trigger_scheduler().start()
        logger.info("Workflow trigger scheduler started")
    except Exception:
        logger.exception("Failed to start workflow trigger scheduler")

    # ── Event Bus ──────────────────────────────────────────
    event_bus = None
    try:
        from dash_backend.events.event_bus import get_event_bus
        event_bus = get_event_bus()
        await event_bus.start()
        logger.info("Event Bus started")
    except Exception:
        logger.exception("Failed to start Event Bus")

    # Workflow event bridge: subscribes the engine's event triggers to the
    # bus and starts the real producers (decisions.md #57). Started right
    # after the bus so subscriptions exist before anything publishes.
    # Non-critical: a failure logs and continues — cron/webhook triggers
    # and manual runs are unaffected.
    try:
        from dash_backend.services.workflow_event_bridge import get_workflow_event_bridge
        await get_workflow_event_bridge().start()
        logger.info("Workflow event bridge started")
    except Exception:
        logger.exception("Failed to start workflow event bridge")

    # Self-healing loop (Phase 2, decisions.md #59): periodic detect →
    # repair → verify cycles. Non-critical: a failure logs and continues.
    try:
        from dash_backend.self_heal import get_self_healing_loop
        await get_self_healing_loop().start()
        logger.info("Self-healing loop started")
    except Exception:
        logger.exception("Failed to start self-healing loop")

    # Guardian (Phase 4, decisions.md #60): defensive security monitoring —
    # listening-port diffing, suspicious-process patterns, failed-login
    # bursts. Detection only; heavy response stays manual. Non-critical.
    try:
        from dash_backend.security.guardian import get_guardian

        import os as _os

        if _os.environ.get("DASH_GUARDIAN_ENABLED", "1") != "0":
            await get_guardian().start()
            logger.info("Guardian started")
        else:
            logger.info("Guardian disabled via DASH_GUARDIAN_ENABLED=0")
    except Exception:
        logger.exception("Failed to start Guardian")

    # Vision watcher (Phase 1 extension, decisions.md #62): periodic camera
    # watch that recognizes enrolled persons and reports honestly through
    # the agent's working memory, the event bus, and the audit log.
    # Non-critical: a failure logs and continues.
    try:
        from dash_backend.vision.watcher import get_vision_watcher

        if _os.environ.get("DASH_VISION_WATCHER_ENABLED", "1") != "0":
            await get_vision_watcher().start()
            logger.info("Vision watcher started")
        else:
            logger.info("Vision watcher disabled via DASH_VISION_WATCHER_ENABLED=0")
    except Exception:
        logger.exception("Failed to start vision watcher")

    # Always-listening wake-word loop (decisions.md #86): server-side mic
    # capture → VAD → "hey dash" → Whisper → REAL chat path → TTS reply.
    # Strictly opt-in (the loop holds the microphone); disabled by default,
    # a failed start logs and continues — never blocks boot.
    try:
        from dash_backend.voice_system.always_listening import get_wake_loop

        wake_loop = get_wake_loop()
        if wake_loop.enabled:
            result = await wake_loop.start()
            logger.info("Wake-word loop start: %s", result)
        else:
            logger.info("Wake-word loop disabled (set DASH_WAKE_LOOP_ENABLED=1 to enable)")
    except Exception:
        logger.exception("Failed to start wake-word loop")

    # ── System Services ────────────────────────────────────
    try:
        from dash_backend.services.system.scheduler import get_system_scheduler
        from dash_backend.services.system.health_monitor import get_health_monitor
        from dash_backend.services.system.metrics import get_metrics_collector
        from dash_backend.services.system.resource_manager import get_resource_manager
        from dash_backend.services.system.cache_manager import get_cache_manager
        # AI Provider health monitor (never blocks startup)
        from dash_backend.services.ai.provider_health_monitor import get_ai_provider_health_monitor
        from dash_backend.services.supabase import get_supabase_service
        await get_system_scheduler().start()
        await get_health_monitor().start()
        await get_metrics_collector().start()
        await get_resource_manager().start()
        await get_cache_manager().start()
        # Start AI provider health monitor - this never blocks startup
        await get_ai_provider_health_monitor().start()
        # Optional cloud connectivity is non-critical and never blocks startup.
        get_health_monitor().register_check(
            "supabase",
            get_supabase_service().health_monitor_check,
            interval_seconds=60.0,
            timeout=6.0,
            critical=False,
        )
        # Warm the shared SystemMonitor snapshot cache so /system/telemetry
        # and /system/stats answer instantly instead of collecting on demand.
        from dash_backend.services.system.system_monitor import get_system_monitor

        await get_system_monitor().start_background_collection()
        logger.info("System services started")
    except Exception:
        logger.exception("Failed to start system services")

    # ── Enhanced Sync Service ──────────────────────────────
    try:
        from dash_backend.sync.enhanced_service import get_enhanced_sync_service
        await get_enhanced_sync_service().start()
        logger.info("Enhanced Sync Service started")
    except Exception:
        logger.exception("Failed to start Enhanced Sync Service")

    # ── Plugin Manager ─────────────────────────────────────
    try:
        from dash_backend.plugins.manager import get_plugin_manager
        from dash_backend.plugins.hot_reloader import get_plugin_hot_reloader
        await get_plugin_manager().start()
        await get_plugin_hot_reloader().start()
        logger.info("Plugin Manager and Hot Reloader started")
    except Exception:
        logger.exception("Failed to start Plugin Manager")

    # ── Autonomous Agent Services ──────────────────────────
    # DASH_BRAIN_AUTONOMY=0 disables the brain's BACKGROUND machinery
    # (idle proactive goals, self-monitor, status reports). The per-request
    # chat path (brain.handle_chat) is unaffected — it enters via get_brain()
    # from the websocket route, not via brain.start(). Used by benchmarks and
    # hermetic boots so background autonomy doesn't skew latency measurements.
    if os.getenv("DASH_BRAIN_AUTONOMY", "1") == "0":
        logger.info("Autonomous agent background services disabled (DASH_BRAIN_AUTONOMY=0)")
    else:
        try:
            # Resume persisted complex tasks left running by a previous
            # shutdown (decisions.md #90): non-terminal orchestrator tasks
            # reload from task_state.json and continue at their last
            # checkpoint — completed steps are never redone.
            try:
                from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
                resumed = get_task_orchestrator().resume_interrupted()
                if resumed:
                    logger.info("Task orchestrator: resumed %d interrupted task(s)", resumed)
            except Exception:
                logger.exception("Task orchestrator resume failed")
            from dash_backend.autonomous.background_task_manager import get_background_task_manager
            from dash_backend.autonomous.reminder_service import get_reminder_service
            from dash_backend.autonomous.system_monitor_agent import get_system_monitor_agent
            from dash_backend.autonomous.idle_detector import get_idle_detector
            from dash_backend.autonomous.agent_core import get_agent_core
            from dash_backend.autonomous.proactive import get_proactive_agent
            await get_background_task_manager().start()
            await get_reminder_service().start()
            await get_system_monitor_agent().start()
            await get_idle_detector().start()
            # Start the proactive agent (runs during idle periods)
            proactive = get_proactive_agent()
            await proactive.start()
            # Start the autonomous brain (JARVIS orchestrator)
            from dash_backend.autonomous.brain import get_brain
            brain = get_brain()
            await brain.start()
            logger.info("Autonomous agent services started (including brain)")
        except Exception:
            logger.exception("Failed to start autonomous agent services")

    # ── Performance Optimization ───────────────────────────
    try:
        from dash_backend.performance.optimizer import get_performance_optimizer
        from dash_backend.performance.latency_optimizer import get_latency_optimizer
        await get_performance_optimizer().start()
        await get_latency_optimizer().start()
        logger.info("Performance optimizers started")
    except Exception:
        logger.exception("Failed to start performance optimizers")

    # ── Ollama / AI Provider Auto-Start ─────────────────
    try:
        from dash_backend.services.ollama_manager import get_ollama_manager
        ollama_mgr = get_ollama_manager(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            auto_start=True,
        )
        ollama_ready = await ollama_mgr.start()
        if ollama_ready:
            logger.info("Ollama ready with model '%s'", settings.ollama_model)
        else:
            logger.warning("Ollama not ready (state=%s) — AI features will be degraded", ollama_mgr.state.value)
        # Start background health monitor
        await ollama_mgr.start_background_monitor()
    except Exception:
        logger.exception("Failed to initialize Ollama manager")

    # ── Predictive Device Sampler ────────────────────────
    predictive_sampler_task = None
    try:
        from dash_backend.predictive.sampler import start_device_sampler
        predictive_sampler_task = start_device_sampler()
        logger.info("Predictive device sampler started")
    except Exception:
        logger.exception("Failed to start predictive device sampler")

    # Publish startup event
    try:
        if event_bus:
            await event_bus.publish_sync(
                topic="system.startup",
                data={"env": settings.env, "debug": settings.debug},
                source="main",
            )
    except Exception:
        logger.exception("Failed to publish startup event")

    yield

    # ── Shutdown ───────────────────────────────────────────
    # Wake loop first: it holds the microphone (PortAudio) and a task
    # blocked in to_thread reads — releasing both before anything else.
    try:
        from dash_backend.voice_system.always_listening import get_wake_loop

        await get_wake_loop().shutdown()
    except Exception:
        logger.exception("Failed to shut down wake-word loop")
    try:
        # Close pooled httpx clients (Ollama/embeddings keep-alive sockets).
        from dash_backend.http_client import close_shared_clients

        await close_shared_clients()
    except Exception:
        logger.exception("Failed to close shared httpx clients")
    try:
        if event_bus:
            await event_bus.publish_sync(
                topic="system.shutdown",
                data={"reason": "normal_shutdown"},
                source="main",
            )
            await event_bus.stop()
    except Exception:
        logger.exception("Failed during event bus shutdown")

    if supabase_sync_task is not None:
        supabase_sync_task.cancel()
        try:
            await supabase_sync_task
        except asyncio.CancelledError:
            pass

    if predictive_sampler_task is not None:
        try:
            from dash_backend.predictive.sampler import stop_device_sampler
            stop_device_sampler()
        except Exception:
            pass
        predictive_sampler_task.cancel()
        try:
            await predictive_sampler_task
        except asyncio.CancelledError:
            pass

    if executive_worker_task is not None:
        executive_worker_task.cancel()
        try:
            await executive_worker_task
        except asyncio.CancelledError:
            pass

    # Cancel pending warm-up (#136) if still running.
    try:
        from dash_backend.llm.warmup import stop_model_warmup

        stop_model_warmup()
    except Exception:
        logger.debug("warm-up shutdown skipped", exc_info=True)

    # Stop the singleton background task manager — it is reused across
    # lifespans (tests boot several apps per process), so it must be stopped
    # here, and its stop must be bounded.
    try:
        from dash_backend.autonomous.background_task_manager import (
            get_background_task_manager,
        )

        await get_background_task_manager().stop()
    except Exception:
        logger.exception("Failed to stop background task manager")

    # Close the shared httpx clients last: any in-flight request (e.g. a
    # warm-up POST to an unreachable Ollama) must not hold shutdown open.
    try:
        from dash_backend.http_client import close_shared_clients

        await close_shared_clients()
    except Exception:
        logger.exception("Failed to close shared httpx clients")

    try:
        if scheduler:
            await scheduler.stop()
    except Exception:
        logger.exception("Failed to stop automation scheduler")

    try:
        from dash_backend.services.workflow_builder import get_workflow_trigger_scheduler
        await get_workflow_trigger_scheduler().stop()
    except Exception:
        logger.exception("Failed to stop workflow trigger scheduler")

    try:
        from dash_backend.services.workflow_event_bridge import get_workflow_event_bridge
        await get_workflow_event_bridge().stop()
    except Exception:
        logger.exception("Failed to stop workflow event bridge")

    try:
        from dash_backend.self_heal import get_self_healing_loop
        await get_self_healing_loop().stop()
    except Exception:
        logger.exception("Failed to stop self-healing loop")

    try:
        from dash_backend.security.guardian import get_guardian
        await get_guardian().stop()
    except Exception:
        logger.exception("Failed to stop Guardian")

    try:
        from dash_backend.vision.watcher import get_vision_watcher
        await get_vision_watcher().stop()
    except Exception:
        logger.exception("Failed to stop vision watcher")

    try:
        from dash_backend.services.system.scheduler import get_system_scheduler
        await get_system_scheduler().stop()
    except Exception:
        logger.exception("Failed to stop system scheduler")

    try:
        from dash_backend.sync.enhanced_service import get_enhanced_sync_service
        await get_enhanced_sync_service().stop()
    except Exception:
        logger.exception("Failed to stop Enhanced Sync Service")

    try:
        from dash_backend.plugins.manager import get_plugin_manager
        from dash_backend.plugins.hot_reloader import get_plugin_hot_reloader
        await get_plugin_manager().stop()
        await get_plugin_hot_reloader().stop()
    except Exception:
        logger.exception("Failed to stop Plugin Manager")

    try:
        from dash_backend.autonomous.reminder_service import get_reminder_service
        from dash_backend.autonomous.system_monitor_agent import get_system_monitor_agent
        from dash_backend.autonomous.idle_detector import get_idle_detector
        await get_reminder_service().stop()
        await get_system_monitor_agent().stop()
        await get_idle_detector().stop()
    except Exception:
        logger.exception("Failed to stop autonomous services")

    try:
        from dash_backend.performance.optimizer import get_performance_optimizer
        from dash_backend.performance.latency_optimizer import get_latency_optimizer
        await get_performance_optimizer().stop()
        await get_latency_optimizer().stop()
    except Exception:
        logger.exception("Failed to stop performance optimizers")

    logger.info("DASH AI OS backend stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    if settings.is_development:
        application.docs_url = f"{settings.api_prefix}/docs"
        application.redoc_url = f"{settings.api_prefix}/redoc"
    else:
        application.docs_url = None
        application.redoc_url = None
        application.openapi_url = None

    # CORS middleware. Two mechanisms compose (decisions.md #75):
    #   - allow_origins: explicit list from DASH_CORS_ORIGINS_RAW — the
    #     mechanism for remote hosts (Tauri, emulator, fly.dev);
    #   - allow_origin_regex: any http(s) localhost/127.0.0.1 port when
    #     cors_localhost_dev is on (default) — browser dev on this machine
    #     is trusted regardless of which port its dev server drifted to.
    # The regex works WITH allow_credentials: starlette reflects the
    # request origin instead of emitting a literal "*" (which browsers
    # reject on credentialed requests), so preflights answer 200 and the
    # ACAO header stays per-origin.
    localhost_regex = (
        r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
        if settings.cors_localhost_dev
        else None
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=localhost_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            response: Response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if settings.env == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ws: wss:"
            return response

    application.add_middleware(SecurityHeadersMiddleware)

    # Global rate limiting middleware
    from dash_backend.security.rate_limiter import get_api_limiter
    _api_limiter = get_api_limiter()

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Skip rate limiting for health checks and docs
            if request.url.path in ("/health", "/docs", "/openapi.json"):
                return await call_next(request)
            client = request.client.host if request.client else "unknown"
            if not await _api_limiter.allow(client):
                from starlette.responses import JSONResponse
                return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please try again later."})
            return await call_next(request)

    application.add_middleware(RateLimitMiddleware)

    # Include API router
    application.include_router(api_router, prefix=settings.api_prefix)

    # Include health router at root level
    from dash_backend.api.routes.health import router as health_router
    application.include_router(health_router, tags=["health"])

    # Production sanity checks
    if settings.is_development is False:
        if settings.debug:
            logger.warning("Debug mode is enabled in non-development environment")
        if settings.jwt_secret_key is None or settings.jwt_secret_key == "changeme":
            logger.warning("JWT secret key is not configured securely")
            if settings.env in ("production", "staging"):
                raise RuntimeError(
                    "DASH_JWT_SECRET_KEY must be set to a strong random value in production"
                )
        if "sqlite" in settings.database_url:
            logger.warning("Using SQLite database in non-development environment")
        cors_origins = settings.cors_origins
        if "*" in cors_origins:
            if settings.env == "production":
                raise RuntimeError("Wildcard CORS origin '*' is not allowed in production")
            logger.warning("Wildcard CORS origin '*' is not recommended in production")

    return application


def run() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()
    import sys
    import uvicorn

    is_frozen = getattr(sys, "frozen", False)
    use_reload = settings.is_development and not is_frozen and not settings.debug
    if use_reload:
        # uvicorn requires an import string for reload mode
        uvicorn.run(
            "dash_backend.main:app",
            host=settings.host,
            port=settings.port,
            reload=True,
            log_level=settings.log_level.lower(),
        )
    else:
        uvicorn.run(
            app,
            host=settings.host,
            port=settings.port,
            reload=False,
            log_level=settings.log_level.lower(),
        )


app = create_app()

if __name__ == "__main__":
    run()
