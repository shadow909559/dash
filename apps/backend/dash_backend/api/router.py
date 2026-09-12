# -*- coding: utf-8 -*-
"""Top-level API router."""

from fastapi import APIRouter

from dash_backend.api.routes.auth import router as auth_router
from dash_backend.api.routes.conversations import router as conversations_router
from dash_backend.api.routes.health import router as health_router
from dash_backend.api.routes.memories import router as memories_router
from dash_backend.api.routes.websocket import router as websocket_router
from dash_backend.api.routes.projects import router as projects_router
from dash_backend.api.routes.notifications import router as notifications_router
from dash_backend.api.routes.automation_rules import router as automation_rules_router
from dash_backend.rag.router import router as rag_router
from dash_backend.automation.router import router as automation_router
from dash_backend.personal import router as personal_router
from dash_backend.sync.router import router as sync_router
from dash_backend.api.routes.system_ws import router as system_ws_router
from dash_backend.api.routes.remote_desktop import router as remote_desktop_router
from dash_backend.api.routes.ai_os import router as ai_os_router
from dash_backend.api.routes.desktop_control import router as desktop_control_router
from dash_backend.api.routes.window_manager import router as window_manager_router
from dash_backend.api.routes.files_rest import router as files_rest_router
from dash_backend.api.routes.phone import router as phone_router
from dash_backend.api.routes.image_upload import router as image_upload_router
from dash_backend.api.routes.file_transfer import router as file_transfer_router
from dash_backend.api.routes.orchestrator import router as orchestrator_router
from dash_backend.api.routes.ecosystem import router as ecosystem_router
from dash_backend.api.routes.monitor import router as monitor_router
from dash_backend.api.routes.companion import router as companion_router
from dash_backend.api.routes.status import router as status_router
from dash_backend.api.routes.obsidian import router as obsidian_router
from dash_backend.api.routes.remote_control import router as remote_control_router
from dash_backend.neural.router import router as neural_router
from dash_backend.api.routes.cloud_relay import router as cloud_relay_router
from dash_backend.api.routes.tunnel import router as tunnel_router
from dash_backend.api.routes.ollama_proxy import router as ollama_proxy_router
from dash_backend.api.routes.ec2_control import router as ec2_control_router
from dash_backend.api.routes.ollama_tunnel import router as ollama_tunnel_router
from dash_backend.autonomous.api import router as agent_router
from dash_backend.api.routes.fine_tuning import router as fine_tuning_router
from dash_backend.api.routes.context import router as context_router
from dash_backend.api.routes.proactive import router as proactive_router
from dash_backend.api.routes.predictive import router as predictive_router
from dash_backend.executive.router import router as executive_router
from dash_backend.api.routes.security import router as security_router
from dash_backend.api.routes.privacy import router as privacy_router
from dash_backend.api.routes.legal import router as legal_router
from dash_backend.api.routes.devtools import router as devtools_router
from dash_backend.api.routes.enhanced_features import router as enhanced_features_router
from dash_backend.api.routes.phase2_features import router as phase2_features_router
from dash_backend.api.routes.phase3_features import router as phase3_features_router
from dash_backend.api.routes.phase4_features import router as phase4_features_router
from dash_backend.api.routes.integrations_all import router as integrations_all_router
from dash_backend.api.routes.integration_connectors import router as integration_connectors_router


api_router = APIRouter()


# Authentication (login, register, token refresh)
api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"],
)


# Health endpoint is at root level, not in api/v1
# api_router.include_router(
#     health_router,
#     tags=["health"],
# )

# Environment context engine (device / project / activity)
api_router.include_router(
    context_router,
    tags=["context"],
)

# Proactive intelligence (suggestions, briefings, end-of-day summary)
api_router.include_router(
    proactive_router,
    tags=["proactive"],
)

# Predictive problem detection (forward-looking risks)
api_router.include_router(
    predictive_router,
    tags=["predictive"],
)

# Executive: goal engine (goals, tasks, dependencies, deadlines)
api_router.include_router(
    executive_router,
    tags=["executive"],
)

# Security: audit log, security settings
api_router.include_router(
    security_router,
    tags=["security"],
)

# Privacy: data export, deletion, inventory
api_router.include_router(
    privacy_router,
    tags=["privacy"],
)

api_router.include_router(
    conversations_router,
    tags=["conversations"],
)

api_router.include_router(
    memories_router,
    prefix="/memory",
    tags=["memory"],
)

api_router.include_router(
    projects_router,
    tags=["projects"],
)

api_router.include_router(
    notifications_router,
    tags=["notifications"],
)

api_router.include_router(
    automation_rules_router,
    tags=["automation-rules"],
)

api_router.include_router(
    rag_router,
    prefix="/rag",
    tags=["rag"],
)

api_router.include_router(
    automation_router,
    prefix="/automation",
    tags=["automation"],
)

# Personal assistant endpoints (single-user personal profile, tasks, reminders)
api_router.include_router(
    personal_router,
    prefix="/personal",
    tags=["personal"],
)

api_router.include_router(
    websocket_router,
    tags=["websocket"],
)

api_router.include_router(
    sync_router,
    tags=["sync"],
)

api_router.include_router(
    system_ws_router,
    tags=["system"],
)

api_router.include_router(
    remote_desktop_router,
    tags=["remote-desktop"],
)

api_router.include_router(
    ai_os_router,
    tags=["ai-os"],
)

api_router.include_router(
    desktop_control_router,
    tags=["desktop"],
)

api_router.include_router(
    window_manager_router,
    tags=["windows"],
)

api_router.include_router(
    files_rest_router,
    tags=["files"],
)

api_router.include_router(
    phone_router,
    tags=["phone"],
)

api_router.include_router(
    image_upload_router,
    tags=["images"],
)

api_router.include_router(
    file_transfer_router,
    tags=["transfer"],
)

api_router.include_router(
    orchestrator_router,
    tags=["orchestrator"],
)

api_router.include_router(
    ecosystem_router,
    tags=["ecosystem"],
)

api_router.include_router(
    monitor_router,
    tags=["monitor"],
)

api_router.include_router(
    companion_router,
    tags=["companion"],
)

# Work/system status aggregation (voice + UI)
api_router.include_router(
    status_router,
    tags=["status"],
)

# Obsidian vault integration
api_router.include_router(
    obsidian_router,
    tags=["obsidian"],
)

# Remote control (Android → Windows service management)
api_router.include_router(
    remote_control_router,
    tags=["remote"],
)

api_router.include_router(
    neural_router,
    tags=["brain"],
)

# Cloud relay — hybrid architecture (Android ↔ Cloud ↔ PC)
api_router.include_router(
    cloud_relay_router,
    tags=["cloud-relay"],
)

# Cloudflare Tunnel status (replaces EC2 for remote access)
api_router.include_router(
    tunnel_router,
    tags=["tunnel"],
)

# EC2 instance control (start/stop from Android)
api_router.include_router(
    ec2_control_router,
    tags=["ec2-control"],
)

# Ollama proxy � Android chat with AI through backend
api_router.include_router(
    ollama_proxy_router,
    tags=["ollama-proxy"],
)

# Ollama tunnel proxy (Cloudflare tunnel for remote access)
api_router.include_router(
    ollama_tunnel_router,
    tags=["ollama-tunnel"],
)

# 3-level LLM fine-tuning
api_router.include_router(
    fine_tuning_router,
    tags=["fine-tuning"],
)

# Autonomous agent — self-operating AI
api_router.include_router(
    agent_router,
    tags=["agent"],
)

# Legal documents (privacy policy, terms, accessibility) — no auth required
api_router.include_router(
    legal_router,
    tags=["legal"],
)

# Development-only tooling (device token for browser preview; env+loopback gated)
api_router.include_router(
    devtools_router,
    prefix="/devtools",
    tags=["devtools"],
)

# Enhanced features: export, shortcuts, analytics, workflows, plugins, knowledge graph, ensemble
api_router.include_router(
    enhanced_features_router,
    tags=["enhanced"],
)

# Phase 2 features: email, security, voice, browser, collaboration, AI, infrastructure
api_router.include_router(
    phase2_features_router,
    tags=["features-v2"],
)

# Phase 3 features: data management, communication, performance, mobile, advanced security
api_router.include_router(
    phase3_features_router,
    tags=["features-v3"],
)

# Phase 4 features: advanced learning, project management, desktop advanced
api_router.include_router(
    phase4_features_router,
    tags=["features-v4"],
)

# OAuth, Integrations, Voice Engine, Browser Automation, Push Notifications
api_router.include_router(
    integrations_all_router,
    tags=["integrations"],
)

# Slack / Telegram / Notion connectors with verified webhook receivers
api_router.include_router(
    integration_connectors_router,
    tags=["connectors"],
)
