"""
RealTimeTransfer
================

Enterprise Cache Interface Protocol

Python 3.13+
"""

from __future__ import annotations

from typing import Any, Protocol


class CacheBackend(Protocol):
    """
    Protocol describing standard async cache backend capabilities.
    """

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.
        """
        ...

    async def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        """
        Set value in cache with optional TTL.
        """
        ...

    async def delete(self, key: str) -> None:
        """
        Delete key from cache.
        """
        ...

    async def clear(self) -> None:
        """
        Clear all cached values.
        """
        ...
