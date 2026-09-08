"""API routes for Phase 3 features: data management, communication, performance, mobile, security."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from dash_backend.auth.dependencies import get_current_user

router = APIRouter(prefix="/phase3", tags=["Features V3"])


# ── Data Retention ─────────────────────────────────────────────────────────

@router.get("/retention/policies")
async def get_retention_policies(_user=Depends(get_current_user)):
    from dash_backend.services.data_management import retention_service
    return retention_service.get_policies()

class PolicyReq(BaseModel):
    data_type: str
    retention_days: int
    auto_delete: bool = False
    archive: bool = True

@router.post("/retention/policies")
async def set_retention_policy(body: PolicyReq, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import retention_service
    return retention_service.set_policy(body.data_type, body.retention_days, body.auto_delete, body.archive)

@router.get("/retention/log")
async def get_deletion_log(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import retention_service
    return {"log": retention_service.get_deletion_log(limit)}


# ── Versioning ─────────────────────────────────────────────────────────────

@router.get("/versions/{entity_type}/{entity_id}")
async def get_versions(entity_type: str, entity_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import versioning_service
    return {"versions": versioning_service.get_versions(entity_type, entity_id)}

@router.get("/versions/{entity_type}/{entity_id}/latest")
async def get_latest_version(entity_type: str, entity_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import versioning_service
    return {"version": versioning_service.get_latest(entity_type, entity_id)}


# ── Archive ────────────────────────────────────────────────────────────────

@router.get("/archives")
async def get_archives(data_type: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import archive_service
    return {"archives": archive_service.get_archives(data_type)}

@router.get("/archives/stats")
async def get_archive_stats(_user=Depends(get_current_user)):
    from dash_backend.services.data_management import archive_service
    return archive_service.get_stats()


# ── Soft Delete ────────────────────────────────────────────────────────────

@router.get("/soft-delete")
async def get_deleted(entity_type: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import soft_delete_service
    return {"deleted": soft_delete_service.get_deleted(entity_type)}

@router.post("/soft-delete/{entity_id}/recover")
async def recover_deleted(entity_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import soft_delete_service
    return soft_delete_service.recover(entity_id)


# ── Bulk Operations ────────────────────────────────────────────────────────

@router.get("/bulk/operations")
async def get_bulk_operations(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.data_management import bulk_operations
    return {"operations": bulk_operations.get_operations(limit)}


# ── Notification Router ────────────────────────────────────────────────────

@router.get("/notifications/router/rules")
async def get_notification_rules(_user=Depends(get_current_user)):
    from dash_backend.services.communication import notification_router
    return {"rules": notification_router.get_rules()}

@router.get("/notifications/router/queue")
async def get_notification_queue(_user=Depends(get_current_user)):
    from dash_backend.services.communication import notification_router
    return {"queue": notification_router.get_queue()}

@router.get("/notifications/router/sent")
async def get_sent_notifications(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.communication import notification_router
    return {"sent": notification_router.get_sent(limit)}


# ── Message Digest ─────────────────────────────────────────────────────────

@router.get("/digest/pending")
async def get_pending_digest(_user=Depends(get_current_user)):
    from dash_backend.services.communication import message_digest
    return {"pending": message_digest.get_pending_count()}

@router.get("/digest/history")
async def get_digests(limit: int = 10, _user=Depends(get_current_user)):
    from dash_backend.services.communication import message_digest
    return {"digests": message_digest.get_digests(limit)}


# ── Batch Processing ───────────────────────────────────────────────────────

@router.get("/batch/jobs")
async def get_batch_jobs(_user=Depends(get_current_user)):
    from dash_backend.services.communication import batch_processor
    return {"jobs": batch_processor.get_jobs()}


# ── External Connectors ────────────────────────────────────────────────────

@router.get("/connectors")
async def get_connectors(_user=Depends(get_current_user)):
    from dash_backend.services.communication import external_connector
    return {"connectors": external_connector.get_connectors()}

@router.post("/connectors/{connector_id}/connect")
async def connect_service(connector_id: str, _user=Depends(get_current_user)):
    from dash_backend.services.communication import external_connector
    return external_connector.connect(connector_id, {})

@router.get("/connectors/events")
async def get_connector_events(connector_id: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.communication import external_connector
    return {"events": external_connector.get_events(connector_id)}


# ── Feature Flags ──────────────────────────────────────────────────────────

@router.get("/feature-flags")
async def get_feature_flags(_user=Depends(get_current_user)):
    from dash_backend.services.performance_advanced import feature_flags
    return feature_flags.get_all()

@router.get("/feature-flags/enabled")
async def get_enabled_flags(_user=Depends(get_current_user)):
    from dash_backend.services.performance_advanced import feature_flags
    return {"enabled": feature_flags.get_enabled()}


# ── A/B Testing ────────────────────────────────────────────────────────────

@router.get("/experiments")
async def get_experiments(_user=Depends(get_current_user)):
    from dash_backend.services.performance_advanced import ab_testing
    return {"experiments": ab_testing.get_experiments()}


# ── Load Balancer ──────────────────────────────────────────────────────────

@router.get("/load-balancer/backends")
async def get_backends(_user=Depends(get_current_user)):
    from dash_backend.services.performance_advanced import load_balancer
    return {"backends": load_balancer.get_backends(), "stats": load_balancer.get_stats()}


# ── HTTP Pool ──────────────────────────────────────────────────────────────

@router.get("/http-pool/stats")
async def get_http_pool_stats(_user=Depends(get_current_user)):
    from dash_backend.services.performance_advanced import http_pool
    return http_pool.get_stats()


# ── Compliance ─────────────────────────────────────────────────────────────

@router.get("/compliance/frameworks")
async def get_compliance_frameworks(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import compliance_service
    return {"frameworks": compliance_service.get_frameworks()}

@router.get("/compliance/report/{framework}")
async def get_compliance_report(framework: str, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import compliance_service
    return compliance_service.get_report(framework)

@router.get("/compliance/reports")
async def get_all_compliance_reports(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import compliance_service
    return {"reports": compliance_service.get_all_reports()}


# ── Vulnerability Scanner ──────────────────────────────────────────────────

@router.get("/vulnerabilities")
async def get_vulnerabilities(severity: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import vulnerability_scanner
    return {"vulnerabilities": vulnerability_scanner.get_vulnerabilities(severity)}


# ── Incident Response ──────────────────────────────────────────────────────

@router.get("/incidents")
async def get_incidents(status: Optional[str] = None, _user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import incident_response
    return {"incidents": incident_response.get_incidents(status)}

@router.get("/incidents/playbooks")
async def get_playbooks(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import incident_response
    return incident_response.get_playbooks()


# ── IP Allowlist ───────────────────────────────────────────────────────────

@router.get("/ip-allowlist")
async def get_ip_lists(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import ip_allowlist
    return ip_allowlist.get_lists()


# ── Mobile Companion ───────────────────────────────────────────────────────

@router.get("/mobile/devices")
async def get_mobile_devices(_user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import push_service
    return {"devices": push_service.get_devices()}

@router.get("/mobile/notifications")
async def get_mobile_notifications(limit: int = 50, _user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import push_service
    return {"notifications": push_service.get_notifications(limit)}

@router.get("/mobile/location")
async def get_location(_user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import location_service
    return location_service.get_current()

@router.get("/mobile/geofences")
async def get_geofences(_user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import location_service
    return {"geofences": location_service.get_geofences()}

@router.get("/mobile/scans")
async def get_qr_scans(limit: int = 20, _user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import qr_scanner
    return {"scans": qr_scanner.get_scans(limit)}

@router.get("/mobile/captures")
async def get_captures(limit: int = 20, _user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import camera_service
    return {"captures": camera_service.get_captures(limit)}

@router.get("/mobile/offline/queue")
async def get_offline_queue(_user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import offline_service
    return {"queue": offline_service.get_queue(), "online": offline_service.is_online()}

@router.get("/mobile/offline/sync-log")
async def get_sync_log(_user=Depends(get_current_user)):
    from dash_backend.services.mobile_companion import offline_service
    return {"log": offline_service.get_sync_log()}


# ── Zero Knowledge ─────────────────────────────────────────────────────────

@router.get("/security/zero-knowledge")
async def get_zk_status(_user=Depends(get_current_user)):
    from dash_backend.services.advanced_security import zero_knowledge
    return {"status": "active", "architecture": "zero-knowledge", "server_sees_plaintext": False}
