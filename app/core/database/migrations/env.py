"""
Alembic environment (DECISION-026).

Two ways in:
- The app (`SchemaMigrator`) hands over an open connection in
  `config.attributes["connection"]`; migrations run on it, inside its transaction.
- The `alembic` command line builds its own engine from the app settings.

Python 3.13+
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from app.core.database.base import Base

config = context.config


def _target_metadata():
    # Every model must be imported for autogenerate / check to see its table
    import app.modules.configurator  # noqa: F401

    return Base.metadata


def _render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Write the app's column types as plain SQLAlchemy ones, so migrations never import app code."""
    from app.core.database.types import GUID, NaiveDateTime

    if type_ == "type" and isinstance(obj, NaiveDateTime):
        return "sa.DateTime()"
    if type_ == "type" and isinstance(obj, GUID):
        return "sa.String(length=36)"
    return False


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    from app.core.database.migrator import UNMANAGED_INDEXES

    return not (type_ == "index" and name in UNMANAGED_INDEXES)


def _configure(connection: Connection, target_metadata=None) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite can only ALTER through "move and copy" batches
        render_as_batch=connection.dialect.name == "sqlite",
        # SQLite reads most types back by affinity (UUID comes back NUMERIC), so
        # only Postgres can compare them
        compare_type=connection.dialect.name != "sqlite",
        render_item=_render_item,
        include_name=include_name,
    )


def _run(connection: Connection, target_metadata=None) -> None:
    _configure(connection, target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_from_settings() -> None:
    from app.config.database import database_config
    from app.core.database.engine import EngineFactory, EngineOptions

    engine = EngineFactory.create(EngineOptions(url=database_config.url))
    try:
        async with engine.begin() as connection:
            await connection.run_sync(_run, _target_metadata())
    finally:
        await engine.dispose()


def run_migrations_offline() -> None:
    from app.config.database import database_config

    context.configure(
        url=database_config.url,
        target_metadata=_target_metadata(),
        literal_binds=True,
        render_as_batch=database_config.is_sqlite,
        render_item=_render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    asyncio.run(_run_from_settings())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
