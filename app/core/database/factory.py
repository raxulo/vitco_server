"""
RealTimeTransfer
================

Enterprise Database Factory

Python 3.13+
"""

from __future__ import annotations

from app.core.config import config
from app.config.database import DatabaseConfig
from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.exceptions import DriverNotFoundError
from app.core.database.manager import DatabaseManager


class DatabaseFactory:
    """
    Stateless enterprise database factory with lazy driver loading.
    """

    __slots__ = (
        "_config",
    )

    def __init__(
        self,
        config_inst: DatabaseConfig,
    ) -> None:
        self._config = config_inst

    def create(self) -> DatabaseManager:
        """
        Create a configured DatabaseManager.
        """
        driver = self._create_driver()
        return DatabaseManager(
            driver=driver,
            config=self._config,
        )

    def _get_driver(self) -> str:
        return self._config.driver

    def _create_driver(self) -> BaseDatabaseDriver:
        """
        Resolve and instantiate the configured driver dynamically.
        """
        driver_name = self._get_driver().lower()

        if driver_name == "sqlite":
            from app.core.database.drivers.sqlite import SQLiteDriver
            return SQLiteDriver()
        elif driver_name == "postgresql":
            from app.core.database.drivers.postgres import PostgreSQLDriver
            return PostgreSQLDriver()
        elif driver_name == "cockroach":
            from app.core.database.drivers.cockroach import CockroachDriver
            return CockroachDriver()
        else:
            raise DriverNotFoundError(
                f"Unsupported database driver '{driver_name}'."
            )