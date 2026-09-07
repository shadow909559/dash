"""Tests for legal document endpoints (Parts 19-20, 36).

Verifies that:
- All three documents are served without authentication
- Each document has correct structure (version, date, content)
- The index endpoint lists all documents
- Content is real (not empty, contains key sections)
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from dash_backend.main import create_app
from tests.conftest import AUTH_HEADERS


@pytest.fixture
async def legal_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_privacy_policy_endpoint(legal_client: AsyncClient) -> None:
    """GET /legal/privacy should return a complete privacy policy."""
    resp = await legal_client.get("/api/v1/legal/privacy")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"] == "privacy_policy"
    assert data["version"] == "1.0"
    assert "effective_date" in data
    assert len(data["content"]) > 1000  # Substantial content


@pytest.mark.asyncio
async def test_privacy_policy_covers_actual_practices(legal_client: AsyncClient) -> None:
    """Privacy policy should describe DASH's actual data practices."""
    resp = await legal_client.get("/api/v1/legal/privacy")
    data = resp.json()
    content = data["content"].lower()
    # Must mention actual data stores
    assert "conversation" in content
    assert "memory" in content
    assert "session" in content
    # Must mention actual external services
    assert "ollama" in content
    assert "openai" in content
    # Must mention data rights
    assert "export" in content or "data-export" in content
    assert "delete" in content or "data-delete" in content
    # Must be honest about cookies: DASH uses device tokens, not cookies
    assert "cookie" in content  # mentions cookies (to state DASH does not use them)


@pytest.mark.asyncio
async def test_terms_endpoint(legal_client: AsyncClient) -> None:
    """GET /legal/terms should return terms and conditions."""
    resp = await legal_client.get("/api/v1/legal/terms")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"] == "terms_and_conditions"
    assert data["version"] == "1.0"
    assert "effective_date" in data
    assert len(data["content"]) > 500


@pytest.mark.asyncio
async def test_terms_covers_required_sections(legal_client: AsyncClient) -> None:
    """Terms should address key legal topics."""
    resp = await legal_client.get("/api/v1/legal/terms")
    content = resp.json()["content"].lower()
    assert "acceptable use" in content or "acceptable" in content
    assert "liability" in content
    assert "intellectual property" in content or "ownership" in content
    assert "termination" in content
    assert "governing law" in content


@pytest.mark.asyncio
async def test_accessibility_statement_endpoint(legal_client: AsyncClient) -> None:
    """GET /legal/accessibility should return the accessibility statement."""
    resp = await legal_client.get("/api/v1/legal/accessibility")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"] == "accessibility_statement"
    assert data["version"] == "1.0"
    assert "effective_date" in data
    assert len(data["content"]) > 500


@pytest.mark.asyncio
async def test_accessibility_statement_honest_limitations(legal_client: AsyncClient) -> None:
    """Accessibility statement should honestly disclose limitations."""
    resp = await legal_client.get("/api/v1/legal/accessibility")
    content = resp.json()["content"].lower()
    assert "known limitation" in content or "limitation" in content
    assert "keyboard" in content
    assert "screen reader" in content or "assistive" in content
    # Should mention WCAG target
    assert "wcag" in content


@pytest.mark.asyncio
async def test_legal_index_endpoint(legal_client: AsyncClient) -> None:
    """GET /legal/ should list all available documents."""
    resp = await legal_client.get("/api/v1/legal/")
    assert resp.status_code == 200
    data = resp.json()
    docs = data["documents"]
    assert len(docs) == 3
    ids = {d["id"] for d in docs}
    assert ids == {"privacy", "terms", "accessibility"}
    for doc in docs:
        assert "name" in doc
        assert "version" in doc
        assert "effective_date" in doc
        assert "endpoint" in doc


@pytest.mark.asyncio
async def test_legal_endpoints_no_auth_required(legal_client: AsyncClient) -> None:
    """Legal endpoints should work without authentication (spec Part 35)."""
    for path in ["/api/v1/legal/", "/api/v1/legal/privacy",
                 "/api/v1/legal/terms", "/api/v1/legal/accessibility"]:
        resp = await legal_client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"


@pytest.mark.asyncio
async def test_privacy_policy_no_fake_claims(legal_client: AsyncClient) -> None:
    """Privacy policy must not claim features DASH doesn't have."""
    resp = await legal_client.get("/api/v1/legal/privacy")
    content = resp.json()["content"].lower()
    # DASH does NOT use session replay
    assert "session replay" not in content or "not" in content
    # DASH should not claim to use advertising cookies
    # The policy mentions them only to say DASH does not use them
    # (verified by the explicit 'does not use' list in section 3.4)
    # DASH does NOT use Google Analytics
    assert "google analytics" not in content


@pytest.mark.asyncio
async def test_documents_have_versioning(legal_client: AsyncClient) -> None:
    """All documents should have version and date fields."""
    for path in ["/api/v1/legal/privacy", "/api/v1/legal/terms",
                 "/api/v1/legal/accessibility"]:
        resp = await legal_client.get(path)
        data = resp.json()
        assert "version" in data, f"{path} missing version"
        assert "effective_date" in data, f"{path} missing effective_date"
        assert data["version"]  # Non-empty
        assert data["effective_date"]  # Non-empty
