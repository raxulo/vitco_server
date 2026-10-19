"""
RealTimeTransfer
================

Enterprise PostgreSQL Driver

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


class PostgreSQLDriver(BaseDatabaseDriver):
    """
    Enterprise PostgreSQL Driver.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return "postgresql"

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

        # Connect to Replica
        if config.database.replica_url and config.database.replica_url != config.database.url:
            replica_options = EngineOptions(
                url=config.database.replica_url,
                echo=config.database.echo,
                pool_size=config.database.pool_size,
                max_overflow=config.database.max_overflow,
                pool_timeout=config.database.pool_timeout,
                pool_recycle=config.database.pool_recycle,
                pool_pre_ping=config.database.pool_pre_ping,
            )
            self._replica_engine = EngineFactory.create(replica_options)
        else:
            self._replica_engine = self._engine

        self._install_events()
        # Initialize session manager with primary and replica engine
        self._session_manager = SessionManager(self.engine, self.replica_engine)
        self._start_telemetry()
        self._connected = True

    async def disconnect(self) -> None:
        if not self.connected:
            return

        await self.engine.dispose()
        if self._replica_engine and self._replica_engine is not self._engine:
            await self._replica_engine.dispose()

        self._engine = None
        self._replica_engine = None
        self._session_manager = None
        self._connected = False

    def _install_events(self) -> None:
        for eng in filter(None, [self.engine, self._replica_engine]):
            @event.listens_for(
                eng.sync_engine,
                "connect",
            )
            def postgres_connect(dbapi_connection, connection_record) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("SET client_encoding='UTF8';")
                cursor.execute("SET TIME ZONE 'UTC';")
                cursor.execute("SET idle_in_transaction_session_timeout='300000';")
                cursor.execute("SET statement_timeout='30000';")
                cursor.close()
