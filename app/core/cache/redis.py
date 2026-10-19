"""
RealTimeTransfer
================

Enterprise Redis Caching Backend

Python 3.13+
"""

from __future__ import annotations

import pickle
from typing import Any

# Future-ready: optional dependency importing
try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


from app.core.resources.interface import Resource


class RedisCacheBackend(Resource):
    """
    Enterprise Redis Caching Backend supporting Serialization and TTLs.
    """

    __slots__ = ("_client", "_redis_url")

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            if aioredis is None:
                raise ImportError(
                    "Optional dependency 'redis' is not installed. "
                    "Run `pip install redis` to use RedisCacheBackend."
                )
            self._client = aioredis.from_url(self._redis_url)
        return self._client

    async def get(self, key: str) -> Any | None:
        client = self._get_client()
        data = await client.get(key)
        if data is None:
            return None
        # Deserialize data
        return pickle.loads(data)

    async def set(self, key: str, value: Any, ttl_seconds: float | None = None) -> None:
        client = self._get_client()
        serialized = pickle.dumps(value)
        if ttl_seconds is not None:
            await client.set(key, serialized, ex=int(ttl_seconds))
        else:
            await client.set(key, serialized)

    async def delete(self, key: str) -> None:
        client = self._get_client()
        await client.delete(key)

    async def clear(self) -> None:
        client = self._get_client()
        await client.flushdb()

    async def startup(self) -> None:
        # Pre-connect client to verify host connectivity at startup
        self._get_client()

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
