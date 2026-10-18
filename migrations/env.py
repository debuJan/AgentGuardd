"""Alembic environment: run migrations against the configured database.

The database URL is taken from the ``DATABASE_URL`` environment variable
(the same one the application uses); ``alembic.ini`` carries no credential.
``target_metadata`` is the SQLAlchemy metadata of the application's models,
so ``alembic revision --autogenerate`` compares against the real schema.
"""
from __future__ import annotations

import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the repo root (this file's parent's parent) is importable so
# ``import src...`` works when alembic runs from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reporting.history.postgres import Base  # noqa: E402

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    # Render/Heroku use "postgres://"; SQLAlchemy 2.x needs "postgresql+psycopg://".
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    if url:
        return url
    # Fallback for local tooling only; never a real credential.
    return "postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/agentguard"


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
