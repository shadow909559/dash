"""Tests for the sync service."""
import pytest
from dash_backend.sync.service import (
    SyncService,
    get_sync_service,
)


@pytest.fixture
def sync_service():
    """Create a fresh sync service for each test."""
    service = SyncService()
    return service


@pytest.mark.asyncio
async def test_register_session(sync_service):
    """Test registering a new sync session."""
    result = await sync_service.register_session(
        session_id="s1",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )
    assert result["status"] == "new"
    assert result["session_id"] == "s1"
    assert result["recovery_count"] == 0
    assert result["requires_full_sync"] is False


@pytest.mark.asyncio
async def test_session_recovery(sync_service):
    """Test session recovery on reconnect."""
    # First registration
    await sync_service.register_session(
        session_id="s1",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )

    # Second registration (recovery)
    result = await sync_service.register_session(
        session_id="s2",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )
    assert result["status"] == "recovered"
    assert result["recovery_count"] == 1


@pytest.mark.asyncio
async def test_full_sync_triggered_after_multiple_recoveries(sync_service):
    """Test that after multiple recoveries, full sync is requested."""
    for i in range(5):
        await sync_service.register_session(
            session_id=f"s{i}",
            client_id="client1",
            client_type="mobile",
            user_id="user1",
        )

    result = await sync_service.register_session(
        session_id="s5",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )
    assert result["requires_full_sync"] is True


@pytest.mark.asyncio
async def test_unregister_session(sync_service):
    """Test unregistering a session."""
    await sync_service.register_session(
        session_id="s1",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )

    await sync_service.unregister_session("client1")
    session = await sync_service.get_session("client1")
    assert session is None


@pytest.mark.asyncio
async def test_heartbeat(sync_service):
    """Test heartbeat recording."""
    await sync_service.register_session(
        session_id="s1",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )

    await sync_service.record_heartbeat("client1")
    stale = await sync_service.get_stale_clients(timeout_seconds=0.001)
    # client should not be stale immediately after heartbeat
    assert "client1" not in stale


@pytest.mark.asyncio
async def test_message_deduplication(sync_service):
    """Test message deduplication."""
    await sync_service.mark_message_seen("client1", "msg1")
    await sync_service.mark_message_seen("client1", "msg2")

    assert await sync_service.is_message_seen("client1", "msg1") is True
    assert await sync_service.is_message_seen("client1", "msg2") is True
    assert await sync_service.is_message_seen("client1", "msg3") is False


@pytest.mark.asyncio
async def test_bulk_message_dedup(sync_service):
    """Test bulk message deduplication."""
    await sync_service.mark_messages_seen_bulk(
        "client1", ["msg1", "msg2", "msg3"]
    )
    assert await sync_service.is_message_seen("client1", "msg1") is True
    assert await sync_service.is_message_seen("client1", "msg3") is True


@pytest.mark.asyncio
async def test_offline_queue(sync_service):
    """Test offline message queue."""
    await sync_service.enqueue_offline_message(
        "client1", {"type": "chat.send", "content": "hello"}
    )
    assert await sync_service.has_offline_messages("client1") is True

    messages = await sync_service.get_offline_messages("client1")
    assert len(messages) == 1
    assert messages[0]["content"] == "hello"
    assert await sync_service.has_offline_messages("client1") is False


@pytest.mark.asyncio
async def test_offline_queue_delivered_on_reconnect(sync_service):
    """Test that queued messages are delivered on recovery."""
    # First register the session
    await sync_service.register_session(
        session_id="s1",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )

    # Queue a message while client is "offline"
    await sync_service.enqueue_offline_message(
        "client1", {"type": "chat.send", "content": "offline msg"}
    )

    # Reconnect - should recover and deliver queued messages
    result = await sync_service.register_session(
        session_id="s2",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )
    # Queued messages should be in the result
    assert len(result.get("queued_messages", [])) == 1


@pytest.mark.asyncio
async def test_vector_clock(sync_service):
    """Test vector clock operations."""
    clock = await sync_service.update_vector_clock(
        "client1", "conversation", "conv1", 1000.0
    )
    assert "client1" in clock
    assert clock["client1"] == 1000000  # converted to milliseconds


@pytest.mark.asyncio
async def test_conflict_detection(sync_service):
    """Test conflict detection."""
    # Register timestamp for a memory
    await sync_service.detect_conflicts(
        "client1",
        "memory",
        [
            {
                "id": "mem1",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    )

    # Client sends older version - should detect conflict
    conflicts = await sync_service.detect_conflicts(
        "client1",
        "memory",
        [
            {
                "id": "mem1",
                "updated_at": "2025-01-01T00:00:00+00:00",
            }
        ],
    )
    assert len(conflicts) == 1
    assert conflicts[0]["entity_id"] == "mem1"


@pytest.mark.asyncio
async def test_conflict_resolution_last_writes_win(sync_service):
    """Test conflict resolution with last-write-wins."""
    local = {
        "id": "mem1",
        "content": "local version",
        "updated_at": "2026-06-01T00:00:00+00:00",
    }
    remote = {
        "id": "mem1",
        "content": "remote version",
        "updated_at": "2026-06-02T00:00:00+00:00",
    }

    resolved = await sync_service.resolve_conflict(
        "memory", "mem1", local, remote
    )
    # Remote has newer timestamp, so it should win
    assert resolved["content"] == "remote version"


@pytest.mark.asyncio
async def test_sync_service_health(sync_service):
    """Test sync service health endpoint."""
    await sync_service.register_session(
        session_id="s1",
        client_id="client1",
        client_type="mobile",
        user_id="user1",
    )
    await sync_service.enqueue_offline_message(
        "client1", {"type": "test"}
    )

    health = await sync_service.get_health()
    assert health["active_sessions"] == 1
    assert health["total_queued_messages"] == 1


@pytest.mark.asyncio
async def test_mark_seen_bulk_empty(sync_service):
    """Test that mark_messages_seen_bulk handles empty list."""
    await sync_service.mark_messages_seen_bulk("client1", [])
    # Should not raise and should not mark anything
    assert await sync_service.is_message_seen("client1", "any") is False


@pytest.mark.asyncio
async def test_get_sync_service_singleton():
    """Test that get_sync_service returns the same instance."""
    service1 = get_sync_service()
    service2 = get_sync_service()
    assert service1 is service2