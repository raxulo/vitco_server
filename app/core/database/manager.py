"""
RealTimeTransfer
================

Enterprise Database Manager

Python 3.13+
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)

from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.session import SessionManager
from app.core.database.transaction import (
    TransactionManager,
    TransactionOptions,
)


class DatabaseManager:
    """
    Enterprise Database Facade.

    This is the ONLY public entry point for the database layer.
    """

    __slots__ = (
        "_driver",
        "_sessions",
        "_transactions",
    )

    def __init__(
        self,
        driver: BaseDatabaseDriver,
    ) -> None:
        self._driver = driver
        self._sessions: SessionManager | None = None
        self._transactions: TransactionManager | None = None

    @property
    def driver(self) -> BaseDatabaseDriver:
        return self._driver

    @property
    def driver_name(self) -> str:
        return self.driver.name

    @property
    def engine(self) -> AsyncEngine:
        return self.driver.engine

    @property
    def sessions(self) -> SessionManager:
        """
        Lazy loaded sessions manager to prevent startup DatabaseConnectionError.
        """
        if self._sessions is None:
            self._sessions = self._driver.session_manager
        return self._sessions

    @property
    def transactions(self) -> TransactionManager:
        """
        Lazy loaded transactions manager to prevent startup DatabaseConnectionError.
        """
        if self._transactions is None:
            self._transactions = TransactionManager(self.sessions)
        return self._transactions

    async def startup(self) -> None:
        await self.driver.start()

    async def shutdown(self) -> None:
        await self.driver.stop()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.sessions.session() as session:
            yield session

    @asynccontextmanager
    async def transaction(
        self,
        options: TransactionOptions | None = None,
    ) -> AsyncIterator[AsyncSession]:
        async with self.transactions.transaction(options) as session:
            yield session

    async def health(self) -> dict[str, Any]:
        return await self.driver.health()

    async def ping(self) -> bool:
        return await self.driver.ping()

    @property
    def connected(self) -> bool:
        return self.driver.connected

    @property
    def in_transaction(self) -> bool:
        return self.transactions.current is not None