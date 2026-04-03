"""Alembic environment configuration for async SQLAlchemy migrations."""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

# Import ORM models so Alembic can detect schema changes
from app.db.orm import Base  # noqa: F401
from app.config import get_settings

# Alembic Config object from alembic.ini
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for 'autogenerate' support
target_metadata = Base.metadata


def get_url() -> str:
    settings = get_settings()
    return settings.database_url


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (generates SQL script)."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations with a live async DB connection."""
    engine = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
