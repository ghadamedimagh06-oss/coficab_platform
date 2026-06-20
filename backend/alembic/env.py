"""Alembic migration environment.

Resolves the database URL from app.config (DATABASE_URL) so migrations target
the same database the app uses — dev and production alike — without a hardcoded
DSN in alembic.ini. target_metadata is the app's Base, with every model
imported so autogenerate sees the full schema.
"""
from logging.config import fileConfig
import os
import sys

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make the backend package importable when alembic runs from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import database_url  # noqa: E402
from app.database import Base  # noqa: E402
import app.models  # noqa: F401,E402  (registers all tables on Base.metadata)

config = context.config

# Inject the resolved URL (config.py enforces prod safety / dev defaults).
config.set_main_option("sqlalchemy.url", database_url() or "")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
