"""Authentication endpoint tests."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dash_backend.auth import models as auth_models
from dash_backend.config import get_settings
from dash_backend.db.base import Base
from dash_backend.db.session import get_db_session
from dash_backend.main import create_app

_ = auth_models


@pytest.fixture
async def auth_app(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[FastAPI]:
    monkeypatch.setenv("DASH_JWT_SECRET_KEY", "test-secret-key")
    get_settings.cache_clear()

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
        get_settings.cache_clear()


@pytest.fixture
async def auth_client(auth_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=auth_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_register_returns_tokens_and_current_user(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "username": "dash-user",
            "password": "correct-password",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["expires_in"] == 900
    assert data["user"]["email"] == "user@example.com"

    me_response = await auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_register_rejects_duplicate_user(auth_client: AsyncClient) -> None:
    payload = {
        "email": "duplicate@example.com",
        "username": "duplicate",
        "password": "correct-password",
    }
    first_response = await auth_client.post("/api/v1/auth/register", json=payload)
    second_response = await auth_client.post("/api/v1/auth/register", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_login_accepts_valid_credentials(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "username": "login-user",
            "password": "correct-password",
        },
    )

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "correct-password",
        },
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["refresh_token"]


@pytest.mark.asyncio
async def test_login_rejects_invalid_credentials(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid@example.com",
            "username": "invalid-user",
            "password": "correct-password",
        },
    )

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid@example.com",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_current_user_requires_access_token(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/me")

    assert response.status_code == 401
