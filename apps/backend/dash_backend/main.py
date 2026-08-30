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
            alembic_command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations applied (alembic upgrade head)")
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

    # Start automation scheduler
    scheduler = None
    try:
        scheduler = get_scheduler()
        scheduler.start()
    except Exception:
        logger.exception("Failed to start automation scheduler")

    # ── Event Bus ──────────────────────────────────────────
    event_bus = None
    try:
        from dash_backend.events.event_bus import get_event_bus
        event_bus = get_event_bus()
        await event_bus.start()
        logger.info("Event Bus started")
    except Exception:
        logger.exception("Failed to start Event Bus")

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
    try:
        from dash_backend.autonomous.background_task_manager import get_background_task_manager
        from dash_backend.autonomous.reminder_service import get_reminder_service
        from dash_backend.autonomous.system_monitor_agent import get_system_monitor_agent
        from dash_backend.autonomous.idle_detector import get_idle_detector
        await get_background_task_manager().start()
        await get_reminder_service().start()
        await get_system_monitor_agent().start()
        await get_idle_detector().start()
        logger.info("Autonomous agent services started")
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

    if executive_worker_task is not None:
        executive_worker_task.cancel()
        try:
            await executive_worker_task
        except asyncio.CancelledError:
            pass

    try:
        if scheduler:
            await scheduler.stop()
    except Exception:
        logger.exception("Failed to stop automation scheduler")

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

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
