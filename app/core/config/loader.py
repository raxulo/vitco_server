"""
RealTimeTransfer
================

Configuration Loader

Python 3.13+
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.config.cache import (
    CacheConfig,
    CacheDriver,
)
from app.core.config.database import (
    DatabaseConfig,
    DatabaseDriver,
)
from app.core.config.logging import (
    LoggingConfig,
)
from app.core.config.security import (
    SecurityConfig,
)
from app.core.config.server import (
    Environment,
    ServerConfig,
)
from app.core.config.settings import Settings
from app.core.config.storage import (
    StorageConfig,
    StorageDriver,
)


class ConfigLoader:
    """
    Enterprise Configuration Loader.

    Loads configuration from

    • defaults

    • environment variables

    • .env (future)

    • secret managers (future)
    """

    @staticmethod
    def getenv(
        key: str,
        default: Any = None,
    ) -> Any:

        return os.getenv(
            key,
            default,
        )

    @staticmethod
    def get_bool(
        key: str,
        default: bool,
    ) -> bool:

        value = os.getenv(key)

        if value is None:
            return default

        return value.lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

    @staticmethod
    def get_int(
        key: str,
        default: int,
    ) -> int:

        value = os.getenv(key)

        if value is None:
            return default

        return int(value)

    @classmethod
    def load(cls) -> Settings:

        server = ServerConfig(

            environment=Environment(
                cls.getenv(
                    "APP_ENV",
                    "development",
                )
            ),

            debug=cls.get_bool(
                "DEBUG",
                False,
            ),
        )

        database = DatabaseConfig(

            driver=DatabaseDriver(

                cls.getenv(
                    "DB_DRIVER",
                    "sqlite",
                )
            ),

            url=cls.getenv(
                "DATABASE_URL",
                "sqlite+aiosqlite:///database.db",
            ),

            echo=cls.get_bool(
                "DB_ECHO",
                False,
            ),
        )

        cache = CacheConfig(

            driver=CacheDriver(

                cls.getenv(
                    "CACHE_DRIVER",
                    "memory",
                )
            )
        )

        storage = StorageConfig(

            driver=StorageDriver(

                cls.getenv(
                    "STORAGE_DRIVER",
                    "local",
                )
            )
        )

        security = SecurityConfig()

        logging = LoggingConfig()

        return Settings(

            server=server,

            database=database,

            cache=cache,

            storage=storage,

            security=security,

            logging=logging,
        )