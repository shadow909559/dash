from __future__ import annotations

import asyncio
import logging
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import your app's metadata
from dash_backend.db.base import Base
from dash_backend.config import get_settings

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Provide Alembic with your model's MetaData object:
target_metadata = Base.metadata


def get_database_url() -> str:
    # Priority:
    # 1) alembic -x database_url=...
    # 2) DASH_DATABASE_URL env var
    # 3) dash_backend default settings.database_url
    x_args = context.get_x_argument(as_dictionary=True)
    if isinstance(x_args, dict):
        override = x_args.get('database_url')
        if override:
            return override

    settings = get_settings()
    return settings.database_url


def _configure_context(connection: Any, *, target_metadata: Any) -> None:
    naming_convention = config.get_section(config.config_ini_section).get('naming_convention') if config.config_ini_section else None

    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=False,
        # Always use naming conventions if provided by SQLAlchemy metadata.
        # (Our project Base.metadata should already include it if defined.)
        process_revision_directives=None,
        **{
            'version_table': config.get_main_option('version_table', 'alembic_version')
        },
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        compare_type=True,
        version_table=config.get_main_option('version_table', 'alembic_version'),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    configuration = config.get_section(config.config_ini_section) or {}
    configuration['sqlalchemy.url'] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _configure_context(connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

