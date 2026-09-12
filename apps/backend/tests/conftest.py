"""Pytest fixtures for backend tests."""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Device identity bootstrap (must run before any request) ──────────
# Tests authenticate exactly like the real desktop client: with the local
# device token, but pointing at a temp identity file.
_TEST_TOKEN = "dash-test-device-token-" + "a" * 32
_IDENTITY_DIR = tempfile.mkdtemp(prefix="dash-test-identity-")
_IDENTITY_PATH = os.path.join(_IDENTITY_DIR, "identity.json")
os.environ["DASH_IDENTITY_FILE"] = _IDENTITY_PATH
with open(_IDENTITY_PATH, "w", encoding="utf-8") as f:
    json.dump(
        {
            "version": 1,
            "install_id": "test-install",
            "device_token": _TEST_TOKEN,
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        f,
    )
os.environ.setdefault("DASH_HOST", "127.0.0.1")
# Hermetic local store: shared feature services (LocalStore consumers) get a
# temp SQLite file instead of the developer's real %LOCALAPPDATA% database.
# Per-test overrides (monkeypatch.setenv) still take precedence.
_TEST_STORE_DIR = tempfile.mkdtemp(prefix="dash-test-store-")
os.environ.setdefault("DASH_LOCAL_STORE", os.path.join(_TEST_STORE_DIR, "dash_local_test.db"))

# Hermetic cloud flags: tests must behave identically on a developer machine
# whose .env enables Supabase sync and in CI where no .env exists. Without
# this, local runs enqueue real outbox events from generic service calls
# (create_goal etc.) and CI does not — a divergence that produced
# environment-dependent failures. Tests that exercise sync explicitly
# monkeypatch the flag themselves, so disabling the default is safe.
os.environ["SUPABASE_ENABLED"] = "false"
os.environ["SUPABASE_SYNC_ENABLED"] = "false"

# Hermetic app database: tests that boot the real app (create_app) must never
# touch the developer's dev database (dash_dev.db) — the live backend keeps it
# locked, causing "sqlite3.OperationalError: database is locked" flakiness,
# and tests would pollute real data. A fresh temp FILE database is used
# (not :memory:, because the app's pooled engine would give each pooled
# connection its own empty in-memory DB). Schema is created once, below, from
# the same metadata the app's alembic migrations model.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="dash-test-db-")
_TEST_DB_PATH = pathlib.Path(_TEST_DB_DIR) / "dash_test.db"
os.environ["DASH_DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH.as_posix()}"

AUTH_HEADERS = {"Authorization": f"Bearer {_TEST_TOKEN}"}

from dash_backend.db.base import Base  # noqa: E402
from dash_backend.db.models.user import User  # noqa: E402
from dash_backend.main import create_app  # noqa: E402


# Create the app-DB schema once per test session, before any test boots the
# app (ASGITransport does not run the lifespan, so alembic never runs in
# tests; the dev DB previously supplied the schema implicitly). A sync
# engine is sufficient — the file is shared with the app's aiosqlite engine.
_sync_test_engine = create_engine(
    f"sqlite:///{_TEST_DB_PATH.as_posix()}", echo=False
)
Base.metadata.create_all(_sync_test_engine)

# Stamp the fresh schema to the latest alembic revision so a full app boot
# (the lifespan test runs `alembic upgrade head` for real) sees an
# already-current database and no-ops instead of re-running revision 1 and
# colliding with create_all's tables ("table agents already exists").
from alembic import command as _alembic_command  # noqa: E402
from alembic.config import Config as _AlembicConfig  # noqa: E402

_alembic_ini = pathlib.Path(__file__).resolve().parents[1] / "alembic.ini"
_alembic_cfg = _AlembicConfig(str(_alembic_ini))
_alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{_TEST_DB_PATH.as_posix()}")
_alembic_command.stamp(_alembic_cfg, "head")


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as ac:
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


# ── Hermetic AI-provider fixtures (decisions.md #44) ────────────
# Why an autouse patch instead of per-test stubs: several test files
# (test_integration, test_typed_memory, …) exercise services that generate
# embeddings. The embedding path calls live endpoints — Ollama (60s timeout
# × two endpoint fallbacks per call) or OpenAI — so on a developer machine
# with Ollama running, tests depend on a live model; in CI they stall for
# minutes per uncached call. Patching at the use sites (services import the
# symbol into their own module namespace) makes every test deterministic
# and instant while keeping provider plumbing covered by unit tests that
# stub the client explicitly.


async def _no_embedding(_text: str):
    return None


@pytest.fixture(autouse=True)
def _hermetic_ai_providers(monkeypatch: pytest.MonkeyPatch):
    """Neutralize live embedding/model calls for every test, everywhere."""
    # get_embedding is imported into these modules' namespaces at module
    # load; patch each binding (monkeypatch restores automatically).
    import dash_backend.memory.service as memory_service
    import dash_backend.services.conversation_embeddings.service as conv_emb_service
    import dash_backend.rag.service as rag_service

    monkeypatch.setattr(memory_service, "get_embedding", _no_embedding)
    monkeypatch.setattr(conv_emb_service, "get_embedding", _no_embedding)
    monkeypatch.setattr(rag_service, "create_embedding", _no_embedding)
    # Anything that slips through (direct module use, lazy imports inside
    # functions) hits the underlying provider stub too.
    import dash_backend.memory.embeddings as memory_embeddings
    import dash_backend.rag.embeddings as rag_embeddings

    monkeypatch.setattr(memory_embeddings, "create_embedding", _no_embedding)
    monkeypatch.setattr(rag_embeddings, "create_embedding", _no_embedding)

