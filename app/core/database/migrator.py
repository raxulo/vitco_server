"""
RealTimeTransfer
================

Schema Migrator (DECISION-026)

Brings the database to the newest Alembic revision when a process connects:

- New database: the migrations create every table.
- Database made by `create_all` before migrations existed (only SQLite in
  practice): it gets the missing tables and columns once and is stamped at the
  baseline, keeping its data.
- Up to date: nothing happens.

On PostgreSQL an advisory lock makes processes that start together take turns.
Errors are raised, never swallowed: a half-migrated database must stop the start.

Python 3.13+
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database.base import Base
from app.core.logging.logger import get_logger

logger = get_logger("schema_migrator")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

BASELINE_REVISION = "0001"

# Indexes made outside the models (exchange `ensure_indexes`); autogenerate must leave them alone
UNMANAGED_INDEXES: frozenset[str] = frozenset({"ix_users_email_lower"})

# Any fixed number; every Quickyee process locks the same one
_ADVISORY_LOCK_KEY = 7_316_220_026

# Columns added to existing tables before migrations existed: (table, column, DDL type)
_LEGACY_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("mkt_orders", "checkout_token", "VARCHAR(36)"),
    # Existing VLCCs are normal (VlccType.NORMAL = 0)
    ("vlcc_master", "vlcc_type", "SMALLINT NOT NULL DEFAULT 0"),
    # Existing MCCs keep showing VLCC names, as they always have
    ("mcc_master", "visible_member", "BOOLEAN NOT NULL DEFAULT TRUE"),
)

_LEGACY_INDEXES: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_mkt_orders_checkout_token ON mkt_orders (checkout_token)",
)


class SchemaMigrator:
    """
    Runs the Alembic migrations on one engine, inside one transaction.
    """

    __slots__ = (
        "_engine",
    )

    def __init__(
        self,
        engine: AsyncEngine,
    ) -> None:
        self._engine = engine

    async def upgrade(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(self._upgrade)

    # ----------------------------------------------------

    @staticmethod
    def _config(connection: Connection) -> Config:
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS_DIR))
        config.attributes["connection"] = connection
        return config

    def _upgrade(self, connection: Connection) -> None:
        if connection.dialect.name == "postgresql":
            # Held until this transaction ends
            connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_LOCK_KEY})

        tables = set(inspect(connection).get_table_names())
        config = self._config(connection)

        if "alembic_version" not in tables and tables & _model_tables():
            logger.info("adopting a database created before migrations; stamping %s", BASELINE_REVISION)
            _adopt_legacy(connection)
            command.stamp(config, BASELINE_REVISION)

        command.upgrade(config, "head")


def _model_tables() -> set[str]:
    # Every model must be registered, or create_all below would miss tables
    import app.modules.configurator  # noqa: F401

    return set(Base.metadata.tables)


def _adopt_legacy(connection: Connection) -> None:
    """Make a `create_all` database match the baseline revision."""
    Base.metadata.create_all(connection)

    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    for table, column, ddl in _LEGACY_COLUMNS:
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing:
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

    if "mkt_orders" in tables:
        for statement in _LEGACY_INDEXES:
            connection.execute(text(statement))
