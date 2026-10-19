"""
RealTimeTransfer
================

Enterprise InMemory Caching Backend

Python 3.13+
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any


from app.core.resources.interface import Resource


@dataclass(slots=True)
class CacheEntry:
    value: Any
    timestamp: float
    ttl: float | None


class InMemoryCacheBackend(Resource):
    """
    Thread-safe and async-safe InMemory Cache Backend with TTL eviction.
    """

    __slots__ = ("_cache", "_lock", "_max_entries")

    def __init__(self, max_entries: int = 10_000) -> None:
        self._cache: dict[str, CacheEntry] = {}
        self._lock = RLock()
        self._max_entries = max_entries

    async def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            if entry.ttl is not None and now - entry.timestamp > entry.ttl:
                del self._cache[key]
                return None

            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._cache) >= self._max_entries:
                self._evict_expired_or_oldest(now)

            self._cache[key] = CacheEntry(
                value=value,
                timestamp=now,
                ttl=ttl_seconds,
            )

    async def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def _evict_expired_or_oldest(self, now: float) -> None:
        # Evict expired keys
        expired = [
            k for k, entry in self._cache.items()
            if entry.ttl is not None and now - entry.timestamp > entry.ttl
        ]
        for k in expired:
            del self._cache[k]

        # Evict oldest if still over capacity
        if len(self._cache) >= self._max_entries:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].timestamp)
            del self._cache[oldest_key]

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        await self.clear()
