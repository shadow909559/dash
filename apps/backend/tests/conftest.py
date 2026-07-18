"""Pytest fixtures for backend tests."""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dash_backend.db.base import Base
from dash_backend.db.models.user import User
from dash_backend.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Database fixtures ──────────────────────────────────────────

# Use in-memory sqlite to avoid cross-test/interpreter file locks and
# uniqueness collisions.
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"




@pytest_asyncio.fixture
async def db_engine():
    # Ensure we have a fresh connection to in-memory DB per test.

    """Create a test database engine."""
    # For in-memory sqlite we don't need on-disk cleanup.


    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    """Create a test database session."""
    session_factory = async_sessionmaker(
        bind=db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user and return it."""
    # Use a unique email per test to avoid UNIQUE constraint failures.
    user = User(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex}@example.com",
        username="testuser",
        password_hash="fakehash",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_id(test_user: User) -> str:
    """Return the test user's id as a string."""
    return str(test_user.id)

