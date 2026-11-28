"""
Optional Redis client (DECISION-032)

A thin wrapper over `redis.asyncio`. Redis is optional: with no URL, or when the server is down,
every call returns `None` / `False` quickly instead of raising, so callers fall back to in-process
behaviour and no request ever fails because of the cache. After an error the client waits a few
seconds before trying again.

Python 3.13+
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

_RETRY_AFTER_S = 5.0


class RedisClient:

    __slots__ = ("_url", "_client", "_healthy", "_retry_at")

    def __init__(self, url: str = "") -> None:
        self._url = (url or "").strip()
        self._client: Any = None
        self._healthy = False
        self._retry_at = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self._url)

    @property
    def healthy(self) -> bool:
        """True when the last call worked."""
        return self.enabled and self._healthy

    def _connection(self) -> Any:
        if not self.enabled or time.monotonic() < self._retry_at:
            return None
        if self._client is None:
            import redis.asyncio as redis

            self._client = redis.from_url(
                self._url, decode_responses=True, socket_timeout=2, socket_connect_timeout=2,
                health_check_interval=30,
            )
        return self._client

    def _failed(self, exc: Exception) -> None:
        if self._healthy or self._retry_at == 0.0:
            logger.warning("Redis unavailable, using in-process fallback: %s", exc)
        self._healthy = False
        self._retry_at = time.monotonic() + _RETRY_AFTER_S

    async def _run(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        client = self._connection()
        if client is None:
            return None
        try:
            result = await getattr(client, operation)(*args, **kwargs)
        except Exception as exc:
            self._failed(exc)
            return None
        self._healthy = True
        return result

    # ------------------------------------------------------------ operations

    async def publish(self, channel: str, message: str) -> bool:
        return await self._run("publish", channel, message) is not None

    async def incr(self, key: str) -> int | None:
        value = await self._run("incr", key)
        return int(value) if value is not None else None

    async def set(self, key: str, value: str, *, ex: int | None = None) -> bool:
        return bool(await self._run("set", key, value, ex=ex))

    async def delete(self, key: str) -> None:
        await self._run("delete", key)

    async def exists(self, key: str) -> bool | None:
        value = await self._run("exists", key)
        return None if value is None else bool(value)

    def pubsub(self) -> Any:
        """A pub/sub object, or None when Redis is off or waiting after an error."""
        client = self._connection()
        return client.pubsub() if client is not None else None

    def mark_failed(self, exc: Exception) -> None:
        """For callers that own a long-lived pub/sub connection."""
        self._failed(exc)

    def mark_healthy(self) -> None:
        self._healthy = True

    async def close(self) -> None:
        client, self._client = self._client, None
        self._healthy = False
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
