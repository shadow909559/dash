"""Device-identity authentication tests.

DASH is a single-user personal system with NO login/register UI. Requests are
authorized by the persistent local device token; anything else must be
rejected with 401 and must NEVER be silently upgraded to a guest identity.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dash_backend.db.base import Base
from dash_backend.db.session import get_db_session
from dash_backend.main import create_app
from tests.conftest import AUTH_HEADERS


@pytest_asyncio.fixture
async def auth_app() -> AsyncIterator[FastAPI]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        yield app
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


@pytest.fixture
async def unauthenticated_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def device_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as client:
        yield client


@pytest.mark.asyncio
async def test_protected_route_rejects_missing_token(unauthenticated_client: AsyncClient) -> None:
    """No Authorization header -> 401. No guest fallback."""
    response = await unauthenticated_client.get("/api/v1/projects")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_rejects_invalid_token(unauthenticated_client: AsyncClient) -> None:
    """A wrong/forged token -> 401, not a provisioned identity."""
    response = await unauthenticated_client.get(
        "/api/v1/projects",
        headers={"Authorization": "Bearer forged-token-not-in-identity-file"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_valid_device_token_authorizes_owner(device_client: AsyncClient) -> None:
    """The real desktop-client flow: valid device token -> authorized request."""
    created = await device_client.post("/api/v1/projects", json={"name": "DASH"})
    assert created.status_code == 201

    listing = await device_client.get("/api/v1/projects")
    assert listing.status_code == 200
    projects = listing.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "DASH"


@pytest.mark.asyncio
async def test_files_route_requires_device_token(unauthenticated_client: AsyncClient) -> None:
    """/files must never serve anonymous requests."""
    response = await unauthenticated_client.get("/api/v1/files/browse", params={"path": "."})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_status_route_requires_device_token(unauthenticated_client: AsyncClient) -> None:
    response = await unauthenticated_client.get("/api/v1/status/overview")
    assert response.status_code == 401
