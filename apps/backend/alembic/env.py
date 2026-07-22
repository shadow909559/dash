"""Alembic environment configuration.

This file handles:
- Model discovery (imports dash_backend.db to register models on Base.metadata)
- Database URL resolution (env var, CLI arg, or settings default)
- Sync driver conversion (asyncpg -> psycopg for Alembic sync engine)
- Online and offline migration modes
"""

from __future__ import annotations

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, inspect, pool, text

# Import all models so they register on Base.metadata
import dash_backend.db  # noqa: F401

# Import your app's metadata
from dash_backend.db.base import Base
from dash_backend.config import get_settings

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

# Provide Alembic with your model's MetaData object:
target_metadata = Base.metadata


def to_sync_dsn(url: str) -> str:
    """Convert async DSN to a sync DSN Alembic can use.

    Alembic runs migrations with a synchronous SQLAlchemy engine.
    We must swap async drivers for their sync equivalents.
    """
    replacements = [
        ("postgresql+asyncpg://", "postgresql+psycopg://"),
        ("sqlite+aiosqlite://", "sqlite://"),
        ("postgresql+asyncp://", "postgresql+psycopg://"),
    ]
    for async_prefix, sync_prefix in replacements:
        if url.startswith(async_prefix):
            return url.replace(async_prefix, sync_prefix, 1)
    return url


def get_database_url() -> str:
    """Resolve the database URL from CLI arg, env var, or settings default."""
    # Priority 1: CLI argument (-x database_url=...)
    try:
        x_args = context.get_x_argument(as_dictionary=True)
        if isinstance(x_args, dict):
            override = x_args.get("database_url")
            if override:
                return override
    except Exception:
        pass

    # Priority 2: Environment variable or settings default
    try:
        settings = get_settings()
        return settings.database_url
    except Exception:
        pass

    # Priority 3: Hardcoded fallback for development
    return "sqlite:///dash_dev.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' (no DB connection) mode.

    SQL is emitted to stdout instead of being executed
    against a live database.
    """
    url = to_sync_dsn(get_database_url())
    logger.info("Offline migration DSN: %s", url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        version_table=config.get_main_option(
            "version_table", "alembic_version"
        ),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database.

    Creates a synchronous engine using the configured URL, then
    executes all pending migrations within a transaction.
    """
    url = to_sync_dsn(get_database_url())
    logger.info("Online migration DSN: %s", url)

    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # Only widen version_num column if alembic_version already exists.
        # On a fresh DB the table will not exist yet.
        if connection.dialect.name == "postgresql":
            inspector = inspect(connection)
            if "alembic_version" in inspector.get_table_names():
                connection.execute(
                    text(
                        "ALTER TABLE alembic_version "
                        "ALTER COLUMN version_num TYPE VARCHAR(64)"
                    )
                )
                connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            version_table=config.get_main_option(
                "version_table", "alembic_version"
            ),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
