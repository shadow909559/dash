"""Ecosystem agent honesty pins (#142).

After the scheduler agent's fake-success fix (#141), the remaining agents
got the same audit: voice claimed ``active: True`` for a wake word it never
checked and streamed nothing; ``_transcribe`` echoed caller text back as a
"transcription"; knowledge's ``local_search`` returned a hardcoded ``[]``
while claiming the capability; security trusted caller-supplied
``granted_permissions`` — authority-by-claim. These pins hold the real
behavior: real state sources, real services, honest failures.
"""

from __future__ import annotations

import base64

import pytest

from dash_backend.agents.ecosystem.voice_agent import VoiceAgent
from dash_backend.agents.ecosystem.knowledge_agent import KnowledgeAgent
from dash_backend.agents.ecosystem.security_agent import SecurityAgent


# ── voice agent ──────────────────────────────────────────────


async def test_wake_word_reports_real_loop_state(monkeypatch):
    """``active`` must come from the real wake loop, never fabricated."""
    agent = VoiceAgent()
    monkeypatch.setattr(
        "dash_backend.voice_system.always_listening._wake_loop", None
    )

    class FakeLoop:
        def get_status(self):
            return {
                "running": False,
                "state": "stopped",
                "wake_word": "hey dash",
                "last_wake_at": "2026-09-22T00:00:00+00:00",
            }

    import dash_backend.voice_system.always_listening as al

    monkeypatch.setattr(al, "get_wake_loop", lambda: FakeLoop())
    out = await agent.execute({"action": "wake_word"})
    assert out["active"] is False  # real state: loop stopped
    assert out["state"] == "stopped"
    assert out["last_wake_at"] == "2026-09-22T00:00:00+00:00"


async def test_transcribe_requires_audio(monkeypatch):
    agent = VoiceAgent()
    with pytest.raises(ValueError, match="audio"):
        await agent.execute({"action": "transcribe", "text": "echo me"})


async def test_transcribe_uses_real_provider(monkeypatch):
    agent = VoiceAgent()
    audio = base64.b64encode(b"fake-pcm").decode()

    class FakeAdapter:
        provider = object()  # non-None -> configured

        async def transcribe(self, data: bytes) -> str:
            assert data == b"fake-pcm"
            return "hello from the real provider"

    import dash_backend.voice_system.providers as vp

    monkeypatch.setattr(vp, "get_speech_provider", lambda name=None: FakeAdapter())
    out = await agent.execute({"action": "transcribe", "audio": audio})
    assert out["text"] == "hello from the real provider"
    assert out["provider"] == "speech"


async def test_transcribe_no_provider_raises(monkeypatch):
    agent = VoiceAgent()

    class Unconfigured:
        provider = None

    import dash_backend.voice_system.providers as vp

    monkeypatch.setattr(vp, "get_speech_provider", lambda name=None: Unconfigured())
    with pytest.raises(ValueError, match="provider"):
        await agent.execute({"action": "transcribe", "audio": base64.b64encode(b"x").decode()})


async def test_synthesize_no_provider_raises(monkeypatch):
    agent = VoiceAgent()

    class Unconfigured:
        provider = None

    import dash_backend.voice_system.providers as vp

    monkeypatch.setattr(vp, "get_tts_provider", lambda name=None: Unconfigured())
    with pytest.raises(ValueError, match="provider"):
        await agent.execute({"action": "synthesize", "text": "hi"})


async def test_synthesize_empty_audio_raises(monkeypatch):
    agent = VoiceAgent()

    class EmptyTTS:
        provider = object()

        async def synthesize(self, text: str) -> bytes:
            return b""

    import dash_backend.voice_system.providers as vp

    monkeypatch.setattr(vp, "get_tts_provider", lambda name=None: EmptyTTS())
    with pytest.raises(ValueError, match="no audio"):
        await agent.execute({"action": "synthesize", "text": "hi"})


async def test_stream_uses_real_voice_manager():
    """stream must touch the real VoiceManager, not claim streaming."""
    from dash_backend.voice_system.service import get_voice_manager

    agent = VoiceAgent()
    mgr = get_voice_manager()
    try:
        out = await agent.execute({"action": "stream", "session_id": "pin-1"})
        assert out["streaming"] is True
        assert mgr.get_session("pin-1") is not None  # real session exists

        out = await agent.execute(
            {"action": "stream", "session_id": "pin-1", "mode": "stop"}
        )
        assert out["stopped"] is True
        assert mgr.get_session("pin-1") is None  # really removed
    finally:
        mgr.stop_session("pin-1")


async def test_stream_requires_session_id():
    agent = VoiceAgent()
    with pytest.raises(ValueError, match="session_id"):
        await agent.execute({"action": "stream"})


# ── knowledge agent ──────────────────────────────────────────


async def test_local_search_hits_real_knowledge_base(monkeypatch):
    """local_search must query the real KnowledgeBase, not return []."""
    agent = KnowledgeAgent()
    calls = {}

    class FakeKB:
        async def search(self, query, top_k=5):
            calls["query"] = query
            calls["top_k"] = top_k
            from dash_backend.intelligence.knowledge_base import SearchResult, DocumentChunk
            chunk = DocumentChunk(doc_path="notes/x.md", chunk_index=0,
                                  content="grounded answer text")
            return [SearchResult(chunk=chunk, score=0.87)]

        def get_stats(self):
            return {"total_documents": 3, "total_chunks": 42,
                    "indexed_paths": 3, "last_index_time": 1.0}

    import dash_backend.intelligence.knowledge_base as kbmod

    monkeypatch.setattr(kbmod, "get_knowledge_base", lambda: FakeKB())
    out = await agent.execute({"action": "search", "query": "grounded", "top_k": 2})
    assert calls == {"query": "grounded", "top_k": 2}
    assert out["results"][0]["doc_path"] == "notes/x.md"
    assert out["results"][0]["score"] == 0.87
    assert out["indexed_documents"] == 3
    assert out["total_chunks"] == 42


async def test_local_search_reports_empty_index_honestly(monkeypatch):
    agent = KnowledgeAgent()

    class EmptyKB:
        async def search(self, query, top_k=5):
            return []

        def get_stats(self):
            return {"total_documents": 0, "total_chunks": 0,
                    "indexed_paths": 0, "last_index_time": 0.0}

    import dash_backend.intelligence.knowledge_base as kbmod

    monkeypatch.setattr(kbmod, "get_knowledge_base", lambda: EmptyKB())
    out = await agent.execute({"action": "search", "query": "anything"})
    assert out["results"] == []
    assert out["indexed_documents"] == 0  # honest: nothing indexed


async def test_embed_requires_text():
    agent = KnowledgeAgent()
    with pytest.raises(ValueError, match="text"):
        await agent.execute({"action": "embed", "text": ""})


async def test_embed_real_service_success_and_failure(monkeypatch):
    agent = KnowledgeAgent()
    import dash_backend.rag.embeddings as emb

    async def fake_ok(text):
        return [0.1, 0.2, 0.3]

    monkeypatch.setattr(emb, "create_embedding", fake_ok)
    out = await agent.execute({"action": "embed", "text": "hello"})
    assert out["vector"] == [0.1, 0.2, 0.3]
    assert out["dims"] == 3

    async def fake_empty(text):
        return None

    monkeypatch.setattr(emb, "create_embedding", fake_empty)
    with pytest.raises(ValueError, match="no vector"):
        await agent.execute({"action": "embed", "text": "hello"})


async def test_rag_retrieve_requires_user_id():
    agent = KnowledgeAgent()
    with pytest.raises(ValueError, match="user_id"):
        await agent.execute({"action": "retrieve", "query": "q"})


# ── security agent ───────────────────────────────────────────


@pytest.fixture(autouse=True)
def _fresh_permissions(monkeypatch):
    """Isolate PermissionService singleton state per test."""
    import dash_backend.services.permissions as perms

    monkeypatch.setattr(perms.PermissionService, "_instance", None, raising=False)
    yield
    monkeypatch.setattr(perms.PermissionService, "_instance", None, raising=False)


async def test_validate_permission_never_trusts_caller_claims():
    """granted_permissions in the payload must be IGNORED — authority by
    claim is exactly the escalation vector the red-team suite tests."""
    agent = SecurityAgent()
    out = await agent.execute({
        "action": "validate_permission",
        "permission": "system:shutdown",
        "user_id": "attacker",
        "granted_permissions": ["system:shutdown"],  # hostile claim
    })
    assert out["allowed"] is False
    assert out["reason"] == "missing_permission"


async def test_validate_permission_real_store_allow_and_deny():
    from dash_backend.services.permissions import get_permission_service

    agent = SecurityAgent()
    svc = get_permission_service()
    svc.add_always_allowed("owner", "system", "shutdown")
    svc.add_denied_forever("owner", "files", "delete")

    ok = await agent.execute({
        "action": "validate_permission",
        "permission": "system:shutdown",
        "user_id": "owner",
    })
    assert ok["allowed"] is True and ok["reason"] == "granted"

    denied = await agent.execute({
        "action": "validate_permission",
        "permission": "files:delete",
        "user_id": "owner",
    })
    assert denied["allowed"] is False and denied["reason"] == "denied"


async def test_validate_permission_denied_overrides_allow():
    from dash_backend.services.permissions import get_permission_service

    agent = SecurityAgent()
    svc = get_permission_service()
    svc.add_always_allowed("owner", "files", "delete")
    svc.add_denied_forever("owner", "files", "delete")

    out = await agent.execute({
        "action": "validate_permission",
        "permission": "files:delete",
        "user_id": "owner",
    })
    assert out["allowed"] is False and out["reason"] == "denied"


async def test_check_dangerous_still_detects_and_requires_confirmation():
    agent = SecurityAgent()
    out = await agent.execute({"action": "check_dangerous", "command": "rm -rf /"})
    assert out["dangerous"] is True
    assert out["requires_confirmation"] is True


async def test_validate_permission_requires_fields():
    agent = SecurityAgent()
    with pytest.raises(ValueError):
        await agent.execute({"action": "validate_permission", "permission": "x"})
    with pytest.raises(ValueError):
        await agent.execute({"action": "validate_permission", "user_id": "u"})
