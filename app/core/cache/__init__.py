"""
RealTimeTransfer
================

Enterprise Caching Service Package Entrypoint

Python 3.13+
"""

from __future__ import annotations

from app.core.cache.decorator import cached
from app.core.cache.in_memory import InMemoryCacheBackend
from app.core.cache.interface import CacheBackend
from app.core.cache.redis import RedisCacheBackend

# Default global cache instance (In-Memory)
cache: CacheBackend = InMemoryCacheBackend()

__all__ = (
    "cache",
    "InMemoryCacheBackend",
    "RedisCacheBackend",
    "CacheBackend",
    "cached",
)
