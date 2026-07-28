"""
RealTimeTransfer
================

Database Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config.base import BaseConfig


# ==========================================================
# Database Driver
# ==========================================================

class DatabaseDriver(StrEnum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    COCKROACH = "cockroach"


# ==========================================================
# Pool Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class PoolConfig(BaseConfig):
    """
    SQLAlchemy connection pool configuration.
    """

    pool_size: int = 20

    max_overflow: int = 40

    pool_timeout: int = 30

    pool_recycle: int = 1800

    pool_pre_ping: bool = True

    pool_reset_on_return: str = "rollback"


# ==========================================================
# Retry Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class RetryConfig(BaseConfig):
    """
    Database retry policy.
    """

    retries: int = 3

    delay: float = 0.5

    exponential_backoff: bool = True

    max_delay: float = 10.0


# ==========================================================
# SSL Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class SSLConfig(BaseConfig):
    """
    SSL configuration.
    """

    enabled: bool = False

    ca_file: str | None = None

    cert_file: str | None = None

    key_file: str | None = None

    verify_server: bool = True


# ==========================================================
# Database Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class DatabaseConfig(BaseConfig):
    """
    Enterprise database configuration.
    """

    #
    # Driver
    #

    driver: DatabaseDriver = DatabaseDriver.SQLITE

    #
    # URL
    #

    url: str = "sqlite+aiosqlite:///database.db"

    #
    # Debug
    #

    echo: bool = False

    #
    # Connection Timeout
    #

    connect_timeout: int = 30

    #
    # SQL Statement Timeout
    #

    statement_timeout: int = 60

    #
    # Pool
    #

    pool: PoolConfig = PoolConfig()

    #
    # Retry
    #

    retry: RetryConfig = RetryConfig()

    #
    # SSL
    #

    ssl: SSLConfig = SSLConfig()

    #
    # Health Check
    #

    health_query: str = "SELECT 1"

    #
    # Auto Create Tables
    #

    create_tables: bool = False

    #
    # Auto Migration
    #

    run_migrations: bool = False

    #
    # Read Replica
    #

    read_replica_url: str | None = None