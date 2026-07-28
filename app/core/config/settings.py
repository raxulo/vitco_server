"""
RealTimeTransfer
================

Application Settings

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config.base import BaseConfig
from app.core.config.cache import CacheConfig
from app.core.config.database import DatabaseConfig
from app.core.config.logging import LoggingConfig
from app.core.config.security import SecurityConfig
from app.core.config.server import ServerConfig
from app.core.config.storage import StorageConfig


@dataclass(
    slots=True,
    frozen=True,
    kw_only=True,
)
class Settings(BaseConfig):
    """
    Master application configuration.

    Every configuration section is
    available through this object.
    """

    #
    # Server
    #

    server: ServerConfig = ServerConfig()

    #
    # Database
    #

    database: DatabaseConfig = DatabaseConfig()

    #
    # Security
    #

    security: SecurityConfig = SecurityConfig()

    #
    # Storage
    #

    storage: StorageConfig = StorageConfig()

    #
    # Cache
    #

    cache: CacheConfig = CacheConfig()

    #
    # Logging
    #

    logging: LoggingConfig = LoggingConfig()

    #
    # Project
    #

    name: str = "RealTimeTransfer"

    version: str = "1.0.0"

    company: str = "RealTimeTransfer"

    timezone: str = "UTC"

    debug: bool = False