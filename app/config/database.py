"""
RealTimeTransfer
================

Database Configuration

This module contains database-related configuration.

Python : 3.13
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.config.settings import settings


@dataclass(slots=True, frozen=True)
class DatabaseConfig:
    """
    Database Configuration
    """

    url: str
    replica_url: str
    echo: bool
    pool_size: int
    max_overflow: int
    pool_timeout: int
    pool_recycle: int
    pool_pre_ping: bool
    statement_timeout_ms: int

    @property
    def is_sqlite(self) -> bool:
        return self.driver == "sqlite"

    @property
    def driver(self) -> str:
        """
        Dynamically extract driver name from URL.
        """
        scheme = self.url.split(":", 1)[0]
        if "sqlite" in scheme:
            return "sqlite"
        if "postgresql" in scheme:
            return "postgresql"
        if "cockroach" in scheme:
            return "cockroach"
        return "sqlite"


database_config = DatabaseConfig(
    url=settings.DATABASE_URL,
    # Fallback to primary URL if replica is not configured in env
    replica_url=os.getenv("DATABASE_REPLICA_URL", settings.DATABASE_URL),
    echo=settings.DATABASE_ECHO,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    statement_timeout_ms=settings.DATABASE_STATEMENT_TIMEOUT_MS,
)