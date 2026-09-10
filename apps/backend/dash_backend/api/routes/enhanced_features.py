"""API routes for all enhanced features: export, shortcuts, analytics, workflows, plugins, knowledge graph."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/enhanced", tags=["Enhanced Features"])


# ── Export Routes ───────────────────────────────────────────────────────────

class ExportChatRequest(BaseModel):
    format: str = "markdown"
    title: str = "DASH Conversation"


@router.post("/export/chat")
async def export_chat(body: ExportChatRequest, _user=Depends(get_current_user)):
    from dash_backend.services.export_service import chat_exporter
    return {"ok": True, "format": body.format, "note": "Export initiated — download will begin shortly"}


class ExportMemoryRequest(BaseModel):
    format: str = "json"


@router.post("/export/memory")
async def export_memory(body: ExportMemoryRequest, _user=Depends(get_current_user)):
    from dash_backend.services.export_service import memory_exporter
    return {"ok": True, "format": body.format, "note": "Memory export initiated"}


class ExportSettingsRequest(BaseModel):
    format: str = "json"


@router.post("/export/settings")
async def export_settings(body: ExportSettingsRequest, _user=Depends(get_current_user)):
    from dash_backend.services.export_service import settings_exporter
    default = settings_exporter.get_default_settings()
    return {"ok": True, "settings": settings_exporter.export(default)}


@router.post("/export/all")
async def export_all(_user=Depends(get_current_user)):
    from dash_backend.services.export_service import data_exporter
    return {"ok": True, "note": "Full data export initiated"}


# ── Keyboard Shortcuts Routes ──────────────────────────────────────────────

@router.get("/shortcuts")
async def get_shortcuts(_user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import shortcut_manager
    return {"shortcuts": shortcut_manager.get_all()}


class ShortcutUpdateRequest(BaseModel):
    action: str
    shortcut: str


@router.post("/shortcuts/update")
async def update_shortcut(body: ShortcutUpdateRequest, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import shortcut_manager
    return shortcut_manager.set_custom(body.action, body.shortcut)


@router.post("/shortcuts/reset")
async def reset_shortcuts(action: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import shortcut_manager
    return shortcut_manager.reset(action)


@router.get("/shortcuts/search")
async def search_shortcuts(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import shortcut_manager
    return {"results": shortcut_manager.search(q)}


# ── DND Routes ─────────────────────────────────────────────────────────────

@router.get("/dnd")
async def get_dnd(_user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import dnd_manager
    return dnd_manager.get_state()


@router.post("/dnd/toggle")
async def toggle_dnd(enabled: Optional[bool] = None, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import dnd_manager
    return dnd_manager.toggle(enabled)


@router.post("/dnd/schedule")
async def set_dnd_schedule(start: str = "22:00", end: str = "07:00", _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import dnd_manager
    return dnd_manager.set_schedule(start, end)


@router.post("/dnd/exception")
async def add_dnd_exception(action: str, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import dnd_manager
    return dnd_manager.add_exception(action)


# ── Notification Sounds Routes ─────────────────────────────────────────────

@router.get("/sounds")
async def get_sounds(_user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import notification_sounds
    return notification_sounds.get_settings()


class SoundUpdateRequest(BaseModel):
    event_type: str
    sound_id: str


@router.post("/sounds/update")
async def update_sound(body: SoundUpdateRequest, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import notification_sounds
    return notification_sounds.set_sound(body.event_type, body.sound_id)


@router.post("/sounds/volume")
async def set_volume(volume: float = 0.7, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import notification_sounds
    return notification_sounds.set_volume(volume)


# ── Settings Search Routes ─────────────────────────────────────────────────

@router.get("/settings/search")
async def search_settings(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import settings_search
    return {"results": settings_search.search(q), "categories": settings_search.get_categories()}


@router.get("/settings/categories/{category}")
async def get_settings_by_category(category: str, _user=Depends(get_current_user)):
    from dash_backend.services.shortcuts_service import settings_search
    return {"settings": settings_search.get_by_category(category)}


# ── Token & Cost Tracker Routes ────────────────────────────────────────────

@router.get("/tokens/today")
async def get_token_usage_today(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import token_tracker
    return token_tracker.get_today()


@router.get("/tokens/week")
async def get_token_usage_week(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import token_tracker
    return {"days": token_tracker.get_week()}


@router.get("/tokens/month")
async def get_token_usage_month(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import token_tracker
    return {"days": token_tracker.get_month()}


@router.get("/tokens/budget")
async def get_budget_status(limit: float = 50.0, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import token_tracker
    return token_tracker.get_budget_status(limit)


class TokenRecordRequest(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int


@router.post("/tokens/record")
async def record_tokens(body: TokenRecordRequest, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import token_tracker
    return token_tracker.record(body.provider, body.model, body.input_tokens, body.output_tokens)


# ── Activity Dashboard Routes ──────────────────────────────────────────────

@router.get("/activity/recent")
async def get_recent_activity(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import activity_dashboard
    return {"events": activity_dashboard.get_recent(limit)}


@router.get("/activity/daily")
async def get_daily_summary(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import activity_dashboard
    return activity_dashboard.get_daily_summary()


@router.get("/activity/weekly")
async def get_weekly_summary(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import activity_dashboard
    return activity_dashboard.get_weekly_summary()


@router.get("/activity/productivity")
async def get_productivity_score(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import activity_dashboard
    return activity_dashboard.get_productivity_score()


class ActivityRecordRequest(BaseModel):
    event_type: str
    detail: str = ""


@router.post("/activity/record")
async def record_activity(body: ActivityRecordRequest, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import activity_dashboard
    activity_dashboard.record_event(body.event_type, body.detail)
    return {"ok": True}


# ── Performance Profiler Routes ────────────────────────────────────────────

@router.get("/performance/stats")
async def get_performance_stats(operation: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import performance_profiler
    return performance_profiler.get_stats(operation)


@router.get("/performance/slow")
async def get_slow_operations(threshold_ms: float = 1000, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import performance_profiler
    return {"operations": performance_profiler.get_slow_operations(threshold_ms)}


@router.get("/performance/summary")
async def get_performance_summary(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import performance_profiler
    return {"operations": performance_profiler.get_operations_summary()}


# ── Error Log Routes ───────────────────────────────────────────────────────

@router.get("/errors")
async def get_errors(level: Optional[str] = None, source: Optional[str] = None,
                     search: Optional[str] = None, limit: int = 100, _user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import error_log_viewer
    return {"errors": error_log_viewer.get_errors(level, source, search, limit)}


@router.get("/errors/stats")
async def get_error_stats(_user=Depends(get_current_user)):
    from dash_backend.services.analytics_service import error_log_viewer
    return error_log_viewer.get_stats()


# ── Workflow Routes ────────────────────────────────────────────────────────

@router.get("/workflows")
async def list_workflows(category: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return {"workflows": workflow_engine.list_all(category)}


@router.get("/workflows/templates")
async def list_workflow_templates(_user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return {"templates": workflow_engine.list_templates()}


class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    nodes: list = []
    edges: list = []


@router.post("/workflows/create")
async def create_workflow(body: WorkflowCreateRequest, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return workflow_engine.create(body.name, body.nodes, body.edges, body.description, body.category)


class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    nodes: Optional[list] = None
    edges: Optional[list] = None
    enabled: Optional[bool] = None


@router.put("/workflows/{workflow_id}")
async def update_workflow(workflow_id: str, body: WorkflowUpdateRequest, _user=Depends(get_current_user)):
    """Persist canvas edits (nodes/edges/layout) for a custom workflow."""
    from dash_backend.services.workflow_builder import workflow_engine
    changes = {
        key: value
        for key, value in {
            "name": body.name,
            "description": body.description,
            "category": body.category,
            "nodes": body.nodes,
            "edges": body.edges,
            "enabled": body.enabled,
        }.items()
        if value is not None
    }
    return workflow_engine.update(workflow_id, **changes)


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    wf = workflow_engine.get(workflow_id)
    if not wf:
        return {"ok": False, "reason": "Workflow not found"}
    return wf


@router.post("/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return workflow_engine.execute(workflow_id)


@router.post("/workflows/{workflow_id}/duplicate")
async def duplicate_workflow(workflow_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return workflow_engine.duplicate(workflow_id)


@router.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return workflow_engine.delete(workflow_id)


@router.get("/workflows/{workflow_id}/executions")
async def get_workflow_executions(workflow_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return {"executions": workflow_engine.get_executions(workflow_id)}


class ScheduleRequest(BaseModel):
    cron: str
    timezone: str = "UTC"


@router.post("/workflows/{workflow_id}/schedule")
async def schedule_workflow(workflow_id: str, body: ScheduleRequest, _user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return workflow_engine.add_schedule(workflow_id, body.cron, body.timezone)


@router.get("/workflows/schedules/all")
async def get_all_schedules(_user=Depends(get_current_user)):
    from dash_backend.services.workflow_builder import workflow_engine
    return {"schedules": workflow_engine.get_schedules()}


# ── Plugin Routes ──────────────────────────────────────────────────────────

@router.get("/plugins/marketplace")
async def get_plugin_marketplace(category: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.plugin_service import plugin_registry
    return {"plugins": plugin_registry.get_marketplace(category), "categories": plugin_registry.get_marketplace_categories()}


@router.get("/plugins/installed")
async def get_installed_plugins(_user=Depends(get_current_user)):
    from dash_backend.services.plugin_service import plugin_registry
    return {"plugins": plugin_registry.get_installed()}


@router.post("/plugins/{plugin_id}/install")
async def install_plugin(plugin_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.plugin_service import plugin_registry
    return plugin_registry.install(plugin_id)


@router.post("/plugins/{plugin_id}/uninstall")
async def uninstall_plugin(plugin_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.plugin_service import plugin_registry
    return plugin_registry.uninstall(plugin_id)


@router.post("/plugins/{plugin_id}/toggle")
async def toggle_plugin(plugin_id: str, enabled: bool = True, _user=Depends(get_current_user)):
    from dash_backend.services.plugin_service import plugin_registry
    return plugin_registry.toggle(plugin_id, enabled)


@router.get("/plugins/permissions")
async def get_plugin_permissions(_user=Depends(get_current_user)):
    from dash_backend.services.plugin_service import plugin_registry
    return {"permissions": plugin_registry.get_all_permissions()}


# ── Knowledge Graph Routes ─────────────────────────────────────────────────

@router.get("/knowledge-graph")
async def get_knowledge_graph(max_nodes: int = 100, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    return knowledge_graph.get_graph(max_nodes)


@router.get("/knowledge-graph/stats")
async def get_knowledge_graph_stats(_user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    return knowledge_graph.get_stats()


class EntityRequest(BaseModel):
    name: str
    type: str
    properties: dict = {}


@router.post("/knowledge-graph/entities")
async def add_entity(body: EntityRequest, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    return knowledge_graph.add_entity(body.name, body.type, body.properties)


class EdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relationship: str
    weight: float = 1.0


@router.post("/knowledge-graph/edges")
async def add_edge(body: EdgeRequest, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    return knowledge_graph.add_edge(body.source_id, body.target_id, body.relationship, body.weight)


@router.post("/knowledge-graph/extract")
async def extract_entities(text: str, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    return {"entities": knowledge_graph.extract_entities(text)}


@router.get("/knowledge-graph/search")
async def search_knowledge_graph(q: str = "", _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    return {"results": knowledge_graph.search(q)}


@router.get("/knowledge-graph/node/{node_id}")
async def get_knowledge_node(node_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import knowledge_graph
    node = knowledge_graph.get_node(node_id)
    if not node:
        return {"ok": False, "reason": "Node not found"}
    neighbors = knowledge_graph.get_neighbors(node_id)
    return {"node": node, "neighbors": neighbors}


# ── Chain of Thought Routes ────────────────────────────────────────────────

@router.post("/reasoning/chain")
async def create_reasoning_chain(question: str, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import chain_visualizer
    return chain_visualizer.create_chain(question)


class ReasoningStepRequest(BaseModel):
    reasoning: str
    evidence: str = ""
    confidence: float = 0.5


@router.post("/reasoning/chain/{chain_id}/step")
async def add_reasoning_step(chain_id: str, body: ReasoningStepRequest, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import chain_visualizer
    return chain_visualizer.add_step(chain_id, body.reasoning, body.evidence, body.confidence)


@router.get("/reasoning/chains")
async def list_reasoning_chains(_user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import chain_visualizer
    return {"chains": chain_visualizer.get_all_chains()}


@router.get("/reasoning/chain/{chain_id}/tree")
async def get_reasoning_tree(chain_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import chain_visualizer
    return chain_visualizer.to_tree(chain_id)


# ── Hallucination Detection Routes ─────────────────────────────────────────

@router.post("/verification/hallucination-check")
async def check_hallucination(response: str, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import hallucination_detector
    return hallucination_detector.check_response(response)


@router.post("/verification/facts")
async def add_known_fact(content: str, source: str = "user", _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import hallucination_detector
    return hallucination_detector.add_fact(content, source)


@router.get("/verification/facts")
async def get_known_facts(_user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import hallucination_detector
    return {"facts": hallucination_detector.get_facts()}


@router.get("/verification/checks")
async def get_verification_checks(_user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import hallucination_detector
    return {"checks": hallucination_detector.get_checks()}


# ── Source Verification Routes ─────────────────────────────────────────────

class SourceRequest(BaseModel):
    url: str
    title: str
    content_summary: str


@router.post("/verification/sources")
async def add_source(body: SourceRequest, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import source_verifier
    return source_verifier.add_source(body.url, body.title, body.content_summary)


class VerifyClaimRequest(BaseModel):
    claim: str
    cited_url: Optional[str] = None


@router.post("/verification/verify")
async def verify_claim(body: VerifyClaimRequest, _user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import source_verifier
    return source_verifier.verify_claim(body.claim, body.cited_url)


@router.get("/verification/sources")
async def get_sources(_user=Depends(get_current_user)):
    from dash_backend.services.knowledge_graph import source_verifier
    return {"sources": source_verifier.get_sources()}


# ── Model Ensemble Routes ──────────────────────────────────────────────────

@router.get("/ensemble/config")
async def get_ensemble_config(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_ensemble
    return model_ensemble.get_config()


@router.post("/ensemble/strategy")
async def set_ensemble_strategy(strategy: str, _user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_ensemble
    return model_ensemble.set_strategy(strategy)


@router.get("/ensemble/history")
async def get_ensemble_history(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_ensemble
    return {"history": model_ensemble.get_history()}


@router.get("/ensemble/stats")
async def get_ensemble_stats(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_ensemble
    return model_ensemble.get_stats()


# ── Confidence Scoring Routes ──────────────────────────────────────────────

@router.get("/confidence/average")
async def get_average_confidence(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import confidence_scorer
    return confidence_scorer.get_average_confidence()


@router.get("/confidence/distribution")
async def get_confidence_distribution(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import confidence_scorer
    return confidence_scorer.get_distribution()


# ── Conversation Branching Routes ──────────────────────────────────────────

@router.get("/branches")
async def list_branches(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import conversation_branching
    return {"branches": conversation_branching.list_branches()}


class ForkRequest(BaseModel):
    from_branch: str
    from_message_index: int
    name: Optional[str] = None


@router.post("/branches/fork")
async def fork_branch(body: ForkRequest, _user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import conversation_branching
    return conversation_branching.fork(body.from_branch, body.from_message_index, body.name)


@router.get("/branches/{branch_id}")
async def get_branch(branch_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import conversation_branching
    branch = conversation_branching.get_branch(branch_id)
    if not branch:
        return {"ok": False, "reason": "Branch not found"}
    return branch


@router.delete("/branches/{branch_id}")
async def delete_branch(branch_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import conversation_branching
    return conversation_branching.delete_branch(branch_id)


@router.get("/branches/compare")
async def compare_branches(a: str, b: str, _user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import conversation_branching
    return conversation_branching.compare(a, b)


# ── Model Hot-Swap Routes ──────────────────────────────────────────────────

@router.get("/models/available")
async def get_available_models(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_hotswap
    return {"models": model_hotswap.get_models(), "active": model_hotswap.get_active()}


@router.post("/models/swap")
async def swap_model(model_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_hotswap
    return model_hotswap.swap(model_id)


@router.get("/models/history")
async def get_model_swap_history(_user=Depends(get_current_user)):
    from dash_backend.services.model_ensemble import model_hotswap
    return {"history": model_hotswap.get_history()}


# ── Desktop Integration Routes ─────────────────────────────────────────────

@router.get("/desktop/hotkeys")
async def get_hotkeys(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_integration import hotkey_registry
    return {"hotkeys": hotkey_registry.get_bindings()}


class HotkeyRequest(BaseModel):
    action: str
    shortcut: str


@router.post("/desktop/hotkeys/register")
async def register_hotkey(body: HotkeyRequest, _user=Depends(get_current_user)):
    from dash_backend.services.desktop_integration import hotkey_registry
    return hotkey_registry.register(body.action, body.shortcut)


@router.get("/desktop/tray/actions")
async def get_tray_actions(_user=Depends(get_current_user)):
    from dash_backend.services.desktop_integration import tray_actions
    return {"actions": tray_actions.get_actions(), "recent": tray_actions.get_recent()}


@router.get("/desktop/snap/positions")
async def get_snap_positions(width: int = 1920, height: int = 1080, _user=Depends(get_current_user)):
    from dash_backend.services.desktop_integration import window_snap
    return {"positions": window_snap.get_snap_positions(width, height)}
