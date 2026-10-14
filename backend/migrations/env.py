from __future__ import annotations

import os

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.models import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # Explicit override (used by tests and CI) > settings.
    override = config.attributes.get("url") or os.environ.get("ALEMBIC_DATABASE_URL")
    if override:
        return str(override)
    settings = get_settings()
    if settings.migration_database_url is None:
        raise RuntimeError("MIGRATION_DATABASE_URL is not configured (schema-owner role)")
    return settings.migration_database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
