

"""
Enterprise Database Manager

Ultra High Performance

Python 3.13+
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)

from app.config.database import DatabaseConfig

from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.session import SessionManager
from app.core.database.transaction import TransactionManager


class DatabaseManager:

    priority = 10

    __slots__ = (
        "_driver",
        "_config",

        "_session_manager",
        "_transaction_manager",

        "_started",
    )

    def __init__(
        self,
        driver: BaseDatabaseDriver,
        config: DatabaseConfig,
    ) -> None:

        self._driver = driver
        self._config = config

        self._session_manager: SessionManager | None = None
        self._transaction_manager: TransactionManager | None = None

        self._started = False

    # ----------------------------------------------------
    # Startup
    # ----------------------------------------------------

    async def startup(self) -> None:

        if self._started:
            return

        await self._driver.start()

        self._session_manager = SessionManager(
            engine=self._driver.engine,
            replica_engine=self._driver.replica_engine,
        )

        self._transaction_manager = TransactionManager(
            self._session_manager,
        )

        self._started = True

    # ----------------------------------------------------

    async def shutdown(self) -> None:

        if not self._started:
            return

        await self._driver.stop()

        self._started = False

    # ----------------------------------------------------
    # Driver
    # ----------------------------------------------------

    @property
    def driver(self) -> BaseDatabaseDriver:
        return self._driver

    @property
    def engine(self) -> AsyncEngine:
        return self._driver.engine

    @property
    def replica_engine(self) -> AsyncEngine:
        return self._driver.replica_engine

    # ----------------------------------------------------
    # Managers
    # ----------------------------------------------------

    @property
    def sessions(self) -> SessionManager:

        manager = self._session_manager

        if manager is None:
            raise RuntimeError(
                "Database has not started."
            )

        return manager

    @property
    def transactions(self) -> TransactionManager:

        manager = self._transaction_manager

        if manager is None:
            raise RuntimeError(
                "Database has not started."
            )

        return manager

    # ----------------------------------------------------
    # Current Session
    # ----------------------------------------------------

    @property
    def session(self) -> AsyncSession:
        return self.transactions.session

    # ----------------------------------------------------
    # Transaction
    # ----------------------------------------------------

    @asynccontextmanager
    async def transaction(self):

        async with self.transactions.transaction() as session:

            yield session

    # ----------------------------------------------------
    # Session
    # ----------------------------------------------------

    @asynccontextmanager
    async def create_session(self):

        async with self.sessions.session() as session:

            yield session

    # ----------------------------------------------------
    # Health
    # ----------------------------------------------------

    async def ping(self):

        return await self.driver.ping()

    async def health(self):

        return await self.driver.health()

    @property
    def connected(self):

        return self.driver.connected