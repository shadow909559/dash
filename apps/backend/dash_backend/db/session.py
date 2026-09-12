"""Async SQLAlchemy session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dash_backend.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    # SQLite: wait up to 30s for a competing writer (alembic at boot, an
    # admin CLI, a second process) instead of failing instantly with
    # "database is locked". Non-SQLite URLs pass no connect args.
    connect_args={"timeout": 30} if settings.database_url.startswith("sqlite") else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
