"""
RealTimeTransfer
================

Enterprise PostgreSQL Driver

The default database (DECISION-025). Session settings travel with asyncpg's
connect() instead of extra statements on every new connection.

Python 3.13+
"""

from __future__ import annotations

from typing import Any

from app.core.config import config
from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.engine import (
    EngineFactory,
    EngineOptions,
)
from app.core.database.session import SessionManager

# Abort a transaction left open and idle for 5 minutes, so it can't hold locks
_IDLE_IN_TRANSACTION_TIMEOUT_MS = 300_000


def _connect_args() -> dict[str, Any]:
    return {
        "server_settings": {
            "application_name": "quickyee",
            # Naive timestamps hold IST, so func.now() defaults must be IST too
            "timezone": "Asia/Kolkata",
            "statement_timeout": str(config.database.statement_timeout_ms),
            "idle_in_transaction_session_timeout": str(_IDLE_IN_TRANSACTION_TIMEOUT_MS),
        },
    }


def _options(url: str) -> EngineOptions:
    return EngineOptions(
        url=url,
        echo=config.database.echo,
        pool_size=config.database.pool_size,
        max_overflow=config.database.max_overflow,
        pool_timeout=config.database.pool_timeout,
        pool_recycle=config.database.pool_recycle,
        pool_pre_ping=config.database.pool_pre_ping,
        connect_args=_connect_args(),
    )


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

        self._engine = EngineFactory.create(_options(config.database.url))

        # Connect to Replica
        if config.database.replica_url and config.database.replica_url != config.database.url:
            self._replica_engine = EngineFactory.create(_options(config.database.replica_url))
        else:
            self._replica_engine = self._engine

        # Initialize session manager with primary and replica engine
        self._session_manager = SessionManager(self.engine, self.replica_engine)
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
