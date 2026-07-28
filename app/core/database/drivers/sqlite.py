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

        options = EngineOptions(
            url=config.database.url,
            echo=config.database.echo,
        )

        self._engine = EngineFactory.create(options)
        self._install_events()
        self._session_manager = SessionManager(self.engine)
        self._start_telemetry()
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