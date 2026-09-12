"""Async SQLAlchemy session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from dash_backend.config import get_settings

settings = get_settings()

from sqlalchemy import event

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    # SQLite: wait up to 30s for a competing writer (alembic at boot, an
    # admin CLI, a second process) instead of failing instantly with
    # "database is locked". Non-SQLite URLs pass no connect args.
    connect_args={"timeout": 30} if settings.database_url.startswith("sqlite") else {},
)

# SQLite: WAL lets one writer and many readers proceed without lock
# contention between the app workers (outbox, executive) and any second
# DASH process; busy_timeout is a belt-and-braces fallback (decisions.md #49).
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_app_pragmas(dbapi_conn, _record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA busy_timeout=30000")
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
        except Exception:  # pragma: no cover - in-memory DBs reject WAL
            pass
        cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
