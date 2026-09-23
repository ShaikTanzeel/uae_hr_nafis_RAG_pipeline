import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Project root on the path so `import src...` works when Alembic is run from
# the project root (same pattern src/api.py uses).
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from src.db import Base
# Importing src.models (not just Base) is what actually registers every table
# on Base.metadata — a model class only adds itself to the metadata when its
# module has been executed at least once. Without this import, autogenerate
# silently sees an empty metadata and proposes no changes at all, even with
# real model files sitting on disk. src/models/__init__.py itself imports
# every individual model module, so this one line covers all of them.
import src.models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Use our own Settings (single source of truth) instead of the hardcoded
# sqlalchemy.url placeholder in alembic.ini — keeps the DB connection info
# defined in exactly one place. Deliberately MIGRATION_DATABASE_URL (the
# Postgres superuser), NOT settings.DATABASE_URL (the app's restricted
# uae_hr_app role) — see Section I2 in config.py: migrations need to
# CREATE/ALTER tables, a power the restricted role intentionally lacks.
config.set_main_option("sqlalchemy.url", settings.MIGRATION_DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Our ORM models' metadata — this is what lets `alembic revision --autogenerate`
# compare our Python model definitions against the live database and write the
# migration for us, instead of hand-writing every column change.
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
