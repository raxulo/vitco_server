"""
RealTimeTransfer
================

Enterprise CockroachDB Driver

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


class CockroachDriver(BaseDatabaseDriver):
    """
    Enterprise CockroachDB Driver.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return "cockroach"

    async def connect(self) -> None:
        if self.connected:
            return

        options = EngineOptions(
            url=config.database.url,
            echo=config.database.echo,
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow,
            pool_timeout=config.database.pool_timeout,
            pool_recycle=config.database.pool_recycle,
            pool_pre_ping=config.database.pool_pre_ping,
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
        def cockroach_connect(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("SET client_encoding='UTF8';")
            cursor.execute("SET TIME ZONE 'UTC';")
            cursor.execute("SET default_transaction_isolation='serializable';")
            cursor.execute("SET statement_timeout='30000';")
            cursor.close()