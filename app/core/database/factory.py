"""
RealTimeTransfer
================

Enterprise Database Factory

Python 3.13+
"""

from __future__ import annotations

from threading import Lock

from app.core.config import config
from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.drivers.cockroach import CockroachDriver
from app.core.database.drivers.postgres import PostgreSQLDriver
from app.core.database.drivers.sqlite import SQLiteDriver
from app.core.database.exceptions import (
    DriverNotFoundError,
)
from app.core.database.manager import DatabaseManager


class DatabaseFactory:
    """
    Enterprise Database Factory.
    """

    __slots__ = ()

    _instance: DatabaseManager | None = None
    _lock = Lock()

    _drivers: dict[str, type[BaseDatabaseDriver]] = {
        "sqlite": SQLiteDriver,
        "postgresql": PostgreSQLDriver,
        "cockroach": CockroachDriver,
    }

    @classmethod
    def create(cls) -> DatabaseManager:
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            if cls._instance is not None:
                return cls._instance

            driver_name = config.database.driver.lower()
            driver_cls = cls._drivers.get(driver_name)

            if driver_cls is None:
                raise DriverNotFoundError(
                    f"Unsupported database driver '{driver_name}'."
                )

            driver = driver_cls()
            cls._instance = DatabaseManager(driver)
            return cls._instance

    @classmethod
    async def startup(cls) -> DatabaseManager:
        manager = cls.create()
        await manager.startup()
        return manager

    @classmethod
    async def shutdown(cls) -> None:
        if cls._instance is None:
            return
        await cls._instance.shutdown()

    @classmethod
    def reset(cls) -> None:
        """
        Testing only.
        """
        cls._instance = None


database = DatabaseFactory.create()