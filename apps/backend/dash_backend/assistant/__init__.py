"""DASH Assistant package — communication, clients, meetings, authority.

Integrated extension of the real DASH architecture (decisions.md #92):
reuses the EventBus, NotificationService, AuditLogService, the task
orchestrator's atomic-JSON persistence conventions and the existing
auth/router/websocket infrastructure. No second realtime system, no
alternate execution path.
"""
