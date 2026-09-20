"""Client-data isolation tests (master plan §31, decisions.md #120).

The master prompt's requirement: when handling Client A, Client B's
requirements/documents/conversations must not surface — and the LLM
cannot bypass it because scoping is enforced in the retrieval SQL, not
by prompt instructions.

Covers:
  - create_document(client_id=...) tags documents in metadata (no schema
    migration needed)
  - scoped search returns own + untagged general docs, NEVER another
    client's — on both the embedding path and the substring fallback
  - the no-query retrieve_context path is scoped identically
  - unscoped retrieval behaves exactly as before (no regression)
  - ChatSendMessage.client_id travels (additive pydantic field) and the
    wake loop derives the scope from an attached meeting context
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from dash_backend.db.base import Base
from dash_backend.rag.service import create_document, retrieve_context, search_documents

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest.fixture()
async def db_session():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


CLIENT_A = "11111111-1111-1111-1111-111111111111"
CLIENT_B = "22222222-2222-2222-2222-222222222222"


def _doc(client: str | None, marker: str) -> str:
    return (f"Confidential {marker}: quarterly revenue figures, "
            f"roadmap details, and private contact information.")


@pytest.mark.asyncio
async def test_scoped_search_excludes_other_client_documents(db_session, user_id):
    """The §31 core guarantee: handling client A must never surface
    client B's tagged documents."""
    await create_document(db_session, user_id,
                          _doc("A", "ClientA内部的销售额数据"), client_id=CLIENT_A)
    await create_document(db_session, user_id,
                          _doc("B", "ClientB internal revenue"), client_id=CLIENT_B)

    results = await search_documents(db_session, user_id, "revenue",
                                     top_k=10, client_id=CLIENT_A)
    texts = [chunk.chunk_text for chunk, _ in results]
    assert any("ClientA" in t for t in texts), "own client's docs must surface"
    assert not any("ClientB" in t for t in texts), \
        "another client's tagged docs must NEVER surface"


@pytest.mark.asyncio
async def test_scoped_search_includes_untagged_general_documents(db_session, user_id):
    """General owner knowledge (untagged) stays reachable in any scope."""
    await create_document(db_session, user_id,
                          "General company handbook about revenue policy.")
    await create_document(db_session, user_id,
                          _doc("A", "ClientA private revenue"), client_id=CLIENT_A)

    results = await search_documents(db_session, user_id, "revenue",
                                     top_k=10, client_id=CLIENT_A)
    texts = [chunk.chunk_text for chunk, _ in results]
    assert any("handbook" in t for t in texts)
    assert any("ClientA" in t for t in texts)


@pytest.mark.asyncio
async def test_unscoped_search_returns_all_documents(db_session, user_id):
    """No client scope → previous behavior: everything is retrievable."""
    await create_document(db_session, user_id, _doc("A", "ClientA revenue data"),
                          client_id=CLIENT_A)
    await create_document(db_session, user_id, _doc("B", "ClientB revenue data"),
                          client_id=CLIENT_B)

    results = await search_documents(db_session, user_id, "revenue", top_k=10)
    texts = [chunk.chunk_text for chunk, _ in results]
    assert any("ClientA" in t for t in texts)
    assert any("ClientB" in t for t in texts)


@pytest.mark.asyncio
async def test_retrieve_context_no_query_path_is_scoped(db_session, user_id):
    """The recent-chunks path (query=None) obeys the same isolation rule."""
    await create_document(db_session, user_id, _doc("A", "ClientA secret"),
                          client_id=CLIENT_A)
    await create_document(db_session, user_id, _doc("B", "ClientB secret"),
                          client_id=CLIENT_B)

    ctx_b = await retrieve_context(db_session, user_id, client_id=CLIENT_B)
    assert "ClientB" in ctx_b
    assert "ClientA" not in ctx_b, "no-query path must also isolate clients"

    ctx_a = await retrieve_context(db_session, user_id, client_id=CLIENT_A)
    assert "ClientA" in ctx_a and "ClientB" not in ctx_a


@pytest.mark.asyncio
async def test_create_document_tags_client_in_metadata(db_session, user_id):
    doc = await create_document(db_session, user_id, "content",
                                client_id=CLIENT_A)
    assert doc.metadata_["client_id"] == CLIENT_A
    # Explicit metadata is not silently overridden
    doc2 = await create_document(db_session, user_id, "content2",
                                 metadata={"client_id": CLIENT_B},
                                 client_id=CLIENT_A)
    assert doc2.metadata_["client_id"] == CLIENT_B


# ── Propagation: protocol field + wake-loop meeting scope ─────────────


def test_chat_send_message_client_id_travels():
    """Additive protocol field parses and defaults to None (backwards
    compatible with every existing client)."""
    from dash_backend.api.websocket.protocol import ChatSendMessage

    msg = ChatSendMessage(message_id="m1", content="hi", client_id=CLIENT_A)
    assert msg.client_id == CLIENT_A
    legacy = ChatSendMessage(message_id="m2", content="hi")
    assert legacy.client_id is None


def test_wake_loop_scopes_from_meeting_context():
    """An attached meeting with a client_id scopes the wake path; the
    scope resets per command and clears with the context."""
    from dash_backend.voice_system.always_listening import AlwaysListeningLoop

    loop = AlwaysListeningLoop(enabled=False)

    async def runner(text: str) -> str:
        return "ok"

    loop._chat_runner = runner

    # Without a meeting: no scope
    import asyncio
    asyncio.run(loop._dispatch_command("what is the status"))
    assert loop._scoped_client_id is None

    # With a meeting carrying a client_id: scoped
    loop.set_meeting_context({"meeting_id": "m1", "title": "T",
                              "mode": "assisted", "client_id": CLIENT_A})
    asyncio.run(loop._dispatch_command("what is the status"))
    assert loop._scoped_client_id == CLIENT_A

    # Meeting cleared → scope gone
    loop.clear_meeting_context()
    asyncio.run(loop._dispatch_command("what is the status"))
    assert loop._scoped_client_id is None


def test_unscoped_command_does_not_carry_stale_scope():
    """After a scoped command, a new command WITHOUT the meeting wrapper
    must not inherit the scope (reset-per-command discipline)."""
    from dash_backend.voice_system.always_listening import AlwaysListeningLoop
    import asyncio

    loop = AlwaysListeningLoop(enabled=False)

    async def runner(text: str) -> str:
        return "ok"

    loop._chat_runner = runner
    loop._scoped_client_id = CLIENT_B  # simulate a stale value
    asyncio.run(loop._dispatch_command("normal command"))
    assert loop._scoped_client_id is None, \
        "stale scope must reset at every dispatch"
