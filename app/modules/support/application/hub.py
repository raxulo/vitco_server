"""
Support socket hub and presence (Phase 27, REQ-73, REQ-75)

Keeps the open sockets of this process and hands every bus event to the ones allowed to hear it.
A slow client never slows the others: each socket has a bounded queue, and one that falls behind is
closed (it reconnects and catches up from its last id).

Presence is "has an open socket": counted here, mirrored to Redis with an expiry when Redis is up so
other processes (and the push sender of Phase 28) can ask.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.infrastructure.redis_client import RedisClient
from app.modules.support.application.audience import Subscriber, can_receive
from app.modules.support.application.events import TYPING, SupportEvent

logger = logging.getLogger(__name__)

PRESENCE_TTL_S = 60


@dataclass(slots=True, eq=False)
class Connection:
    """One open socket. `queue` holds JSON-ready messages for the sender task."""

    subscriber: Subscriber
    kind: str                                    # "staff" | "app"
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=500))
    overflowed: bool = False

    def send(self, message: dict[str, Any]) -> bool:
        try:
            self.queue.put_nowait(message)
            return True
        except asyncio.QueueFull:
            self.overflowed = True
            return False

    def payload_for(self, event: SupportEvent) -> dict[str, Any]:
        body = event.for_requester() if self.subscriber.is_requester else event.for_staff()
        return {"type": "typing" if event.type == TYPING else "event", "id": event.id, "event": body}


class SocketHub:

    __slots__ = ("_connections", "_max", "_redis")

    def __init__(self, *, max_connections: int, redis: RedisClient | None = None) -> None:
        self._connections: set[Connection] = set()
        self._max = max_connections
        self._redis = redis or RedisClient("")

    def __len__(self) -> int:
        return len(self._connections)

    def add(self, connection: Connection) -> bool:
        if len(self._connections) >= self._max:
            return False
        self._connections.add(connection)
        return True

    def remove(self, connection: Connection) -> None:
        self._connections.discard(connection)

    def is_online(self, user_id: UUID) -> bool:
        return any(c.subscriber.user_id == user_id for c in self._connections)

    async def is_online_anywhere(self, user_id: UUID) -> bool:
        """This process first, then Redis (another process may hold the socket)."""
        if self.is_online(user_id):
            return True
        return bool(await self._redis.exists(f"support:online:{user_id}"))

    async def touch(self, user_id: UUID) -> None:
        await self._redis.set(f"support:online:{user_id}", "1", ex=PRESENCE_TTL_S)

    async def drop_presence(self, user_id: UUID) -> None:
        if not self.is_online(user_id):
            await self._redis.delete(f"support:online:{user_id}")

    def on_event(self, event: SupportEvent) -> None:
        """Bus subscriber: queue the event for every connection that may hear it."""
        for connection in list(self._connections):
            if event.type == TYPING and event.data.get("user_id") == str(connection.subscriber.user_id):
                continue                                   # nobody needs their own typing echoed
            if not can_receive(connection.subscriber, event):
                continue
            if not connection.send(connection.payload_for(event)):
                logger.warning("Support socket too slow, closing it so it can catch up")
