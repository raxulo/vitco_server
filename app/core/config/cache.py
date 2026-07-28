"""
RealTimeTransfer
================

Cache Configuration

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.config.base import BaseConfig


# ==========================================================
# Cache Driver
# ==========================================================

class CacheDriver(StrEnum):

    MEMORY = "memory"

    REDIS = "redis"

    REDIS_CLUSTER = "redis_cluster"


# ==========================================================
# Redis Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class RedisConfig(BaseConfig):
    """
    Redis configuration.
    """

    host: str = "127.0.0.1"

    port: int = 6379

    database: int = 0

    username: str | None = None

    password: str | None = None

    ssl: bool = False

    socket_timeout: float = 5.0

    connect_timeout: float = 5.0

    retry_on_timeout: bool = True

    health_check_interval: int = 30

    max_connections: int = 500


# ==========================================================
# Memory Cache
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class MemoryCacheConfig(BaseConfig):
    """
    In-memory cache.
    """

    max_entries: int = 10000

    default_ttl: int = 300


# ==========================================================
# Cache Policy
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class CachePolicy(BaseConfig):
    """
    Default cache policy.
    """

    default_ttl: int = 300

    key_prefix: str = "rtt"

    compression: bool = False

    statistics: bool = True


# ==========================================================
# Main Cache Configuration
# ==========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class CacheConfig(BaseConfig):
    """
    Enterprise cache configuration.
    """

    driver: CacheDriver = CacheDriver.REDIS

    redis: RedisConfig = RedisConfig()

    memory: MemoryCacheConfig = MemoryCacheConfig()

    policy: CachePolicy = CachePolicy()

    enabled: bool = True