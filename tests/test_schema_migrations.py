"""
Schema migrations (Phase 20, DECISION-026).

The session database (SQLite or, with TEST_DATABASE_URL, PostgreSQL) was built
by the migrations alone, so it is checked against the models. The fresh and
legacy cases use their own SQLite files.

Python 3.13+
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.database.base import Base
from app.core.database.migrator import MIGRATIONS_DIR, UNMANAGED_INDEXES, SchemaMigrator


def _head() -> str:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return ScriptDirectory.from_config(config).get_current_head()


def _version(sync_connection) -> str | None:
    return MigrationContext.configure(sync_connection).get_current_revision()


def _sqlite_engine(path: Path):
    return create_async_engine(f"sqlite+aiosqlite:///{path.as_posix()}")


async def test_session_database_is_at_head_and_matches_the_models(database):
    def check(sync_connection):
        dialect = sync_connection.dialect.name
        context = MigrationContext.configure(
            sync_connection,
            opts={
                "compare_type": dialect != "sqlite",
                "include_name": lambda name, type_, _: not (type_ == "index" and name in UNMANAGED_INDEXES),
            },
        )
        return _version(sync_connection), compare_metadata(context, Base.metadata)

    async with database.transaction() as session:
        version, differences = await session.run_sync(lambda s: check(s.connection()))

    assert version == _head()
    assert differences == []


async def test_new_database_gets_every_table(tmp_path):
    engine = _sqlite_engine(tmp_path / "fresh.db")
    try:
        await SchemaMigrator(engine).upgrade()
        await SchemaMigrator(engine).upgrade()  # second start changes nothing

        async with engine.connect() as connection:
            tables = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
            version = await connection.run_sync(_version)
    finally:
        await engine.dispose()

    assert set(Base.metadata.tables) <= tables
    assert version == _head()


async def test_legacy_database_keeps_its_rows_and_gains_missing_columns(tmp_path):
    engine = _sqlite_engine(tmp_path / "legacy.db")
    message_id = str(uuid4())
    try:
        # A database from before migrations: create_all, no alembic_version, an older mcc_master
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(text("ALTER TABLE mcc_master DROP COLUMN visible_member"))
            await connection.execute(text("DROP TABLE mkt_settings"))
            await connection.execute(
                text(
                    "INSERT INTO outbox_messages (id, event_type, payload, created_at, processed)"
                    " VALUES (:id, 'legacy', '{}', '2026-01-01 10:00:00', 0)"
                ),
                {"id": message_id},
            )

        await SchemaMigrator(engine).upgrade()

        async with engine.connect() as connection:
            columns = await connection.run_sync(lambda c: {col["name"] for col in inspect(c).get_columns("mcc_master")})
            tables = await connection.run_sync(lambda c: set(inspect(c).get_table_names()))
            kept = await connection.scalar(text("SELECT event_type FROM outbox_messages WHERE id = :id"), {"id": message_id})
            version = await connection.run_sync(_version)
    finally:
        await engine.dispose()

    assert "visible_member" in columns
    assert "mkt_settings" in tables
    assert kept == "legacy"
    assert version == _head()


async def test_a_failing_migration_stops_the_start(tmp_path):
    """The old startup patches swallowed every error; the migrator must not."""
    engine = _sqlite_engine(tmp_path / "broken.db")
    try:
        async with engine.begin() as connection:
            # alembic_version points at a revision that does not exist
            await connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
            await connection.execute(text("INSERT INTO alembic_version VALUES ('no_such_revision')"))

        with pytest.raises(Exception, match="no_such_revision"):
            await SchemaMigrator(engine).upgrade()
    finally:
        await engine.dispose()
