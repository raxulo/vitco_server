"""
RealTimeTransfer
================

Enterprise SQLite Driver

Python 3.13+
"""

from __future__ import annotations

from sqlalchemy import event

from app.core.config import config
from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.engine import (
    EngineFactory,
    EngineOptions,
)
from app.core.database.session import SessionManager


class SQLiteDriver(BaseDatabaseDriver):
    """
    Enterprise SQLite Driver.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return "sqlite"

    async def connect(self) -> None:
        if self.connected:
            return

        # Ensure parent directory exists for SQLite
        from pathlib import Path
        url = config.database.url
        if url.startswith("sqlite+aiosqlite:///"):
            db_path = url.replace("sqlite+aiosqlite:///", "")
            if not db_path.startswith(":memory:") and db_path != "":
                path = Path(db_path)
                if not path.is_absolute():
                    from app.config.settings import BASE_DIR
                    path = BASE_DIR / path
                path.parent.mkdir(parents=True, exist_ok=True)

        options = EngineOptions(
            url=config.database.url,
            echo=config.database.echo,
        )

        try:
            self._engine = EngineFactory.create(options)
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "DATABASE_URL points at SQLite, but this Python has no sqlite3 module. "
                "Set a postgresql+asyncpg:// DATABASE_URL in .env.local (see docs/DATABASE.md)."
            ) from exc
        self._install_events()
        self._session_manager = SessionManager(self.engine)

        # Tables and columns come from the Alembic migrations (SchemaMigrator)
        self._connected = True

    async def disconnect(self) -> None:
        if not self.connected:
            return

        await self.engine.dispose()
        self._engine = None
        self._session_manager = None
        self._connected = False

    def _install_events(self) -> None:
        @event.listens_for(
            self.engine.sync_engine,
            "connect",
        )
        def sqlite_connect(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=268435456")
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.execute("PRAGMA optimize")
            cursor.close()