"""
Support event bus (Phase 27, REQ-73, REQ-74, DECISION-032)

Events are published only after the database transaction that caused them has committed
(`after_commit`), and dropped when it rolls back, so a screen never learns about work that did not
happen. Delivery goes through Redis pub/sub when Redis is up (ids from `INCR`, so several processes
agree) and through this process directly when it is not; the switch is automatic both ways.

A bounded in-memory ring keeps the latest events so a client that reconnects with the last id it saw
gets what it missed. If it missed more than the ring holds (or the server restarted) it is told to
reload instead.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from collections.abc import Callable

from sqlalchemy import event as sa_event
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.redis_client import RedisClient
from app.modules.support.application.events import SupportEvent

logger = logging.getLogger(__name__)

CHANNEL = "support:events"
COUNTER = "support:event_id"
_PENDING_KEY = "support_events_pending"

Subscriber = Callable[[SupportEvent], None]


def _inside(transaction, ancestor) -> bool:
    """True when `transaction` is `ancestor` or nested in it."""
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False


class EventBus:

    __slots__ = ("_redis", "_ring", "_subscribers", "_last_id", "_listener", "_listening", "_tasks")

    def __init__(self, redis: RedisClient | None = None, *, buffer: int = 2000) -> None:
        self._redis = redis or RedisClient("")
        self._ring: deque[SupportEvent] = deque(maxlen=max(10, buffer))
        self._subscribers: list[Subscriber] = []
        # Start above any id handed out before a restart, so clients can tell their id is old
        self._last_id = int(time.time() * 1000)
        self._listener: asyncio.Task | None = None
        self._listening = False
        self._tasks: set[asyncio.Task] = set()

    # ------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        if self._redis.enabled and self._listener is None:
            self._listener = asyncio.create_task(self._listen(), name="support-event-listener")

    async def stop(self) -> None:
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.cancel()
            try:
                await listener
            except (asyncio.CancelledError, Exception):
                pass
        for task in list(self._tasks):
            task.cancel()
        self._listening = False
        await self._redis.close()

    @property
    def redis_active(self) -> bool:
        """True while events travel through Redis."""
        return self._listening and self._redis.healthy

    @property
    def latest_id(self) -> int:
        return self._last_id

    def subscribe(self, callback: Subscriber) -> None:
        self._subscribers.append(callback)

    # ------------------------------------------------------------ publishing

    def after_commit(self, session: AsyncSession, event: SupportEvent) -> None:
        """Queue an event on the session: sent when it commits, dropped when it rolls back."""
        sync_session = session.sync_session
        pending = sync_session.info.get(_PENDING_KEY)
        if pending is None:
            pending = []          # (event, the transaction or savepoint it was queued in)
            sync_session.info[_PENDING_KEY] = pending

            def committed(_session) -> None:
                events = [queued for queued, _ in pending]
                pending.clear()
                if events:
                    self._spawn(self.publish_many(events))

            def rolled_back(_session, previous_transaction) -> None:
                # Fires for the whole transaction and for a savepoint. A savepoint rollback means a handler
                # failed but the outer transaction goes on (a form showed the error): forget only what was
                # queued inside it. (`after_rollback` cannot tell the two apart, so it is not used.)
                if previous_transaction.nested:
                    pending[:] = [item for item in pending if not _inside(item[1], previous_transaction)]
                else:
                    pending.clear()

            sa_event.listen(sync_session, "after_commit", committed)
            sa_event.listen(sync_session, "after_soft_rollback", rolled_back)
        current = sync_session.get_nested_transaction() or sync_session.get_transaction()
        pending.append((event, current))

    def _spawn(self, coroutine) -> None:
        try:
            task = asyncio.get_running_loop().create_task(coroutine)
        except RuntimeError:       # no running loop (never in the app); drop rather than fail the request
            coroutine.close()
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def publish_many(self, events: list[SupportEvent]) -> None:
        for event in events:
            try:
                await self.publish(event)
            except Exception:
                logger.exception("Support event could not be published")

    async def publish(self, event: SupportEvent) -> SupportEvent:
        """Give the event an id and deliver it. Never raises because Redis is down."""
        if not event.ephemeral:
            event.id = await self._next_id()
        if self._listening and await self._redis.publish(CHANNEL, event.to_json()):
            return event                 # the listener delivers it, here and in every other process
        self.receive(event)
        return event

    async def _next_id(self) -> int:
        """A unique id above every id seen here.

        The local id is reserved before any await, so two publishes in this process never share one.
        With Redis, the shared counter is lifted to at least that id in one atomic step, so every
        process draws from the same rising sequence (a plain INCR starts at 1, far below the
        time-based local ids, and was never used).
        """
        self._last_id += 1
        local = self._last_id
        if self._listening:
            shared = await self._redis.incr_at_least(COUNTER, local)
            if shared is not None:
                self._last_id = max(self._last_id, shared)
                return shared
            self._last_id += 1          # Redis failed during the call: a fresh id above anything handed out
            return self._last_id
        return local

    def receive(self, event: SupportEvent) -> None:
        """Deliver to this process: store for replay, then call every subscriber."""
        if not event.ephemeral:
            self._last_id = max(self._last_id, event.id)
            self._ring.append(event)
        for callback in list(self._subscribers):
            try:
                callback(event)
            except Exception:
                logger.exception("Support event subscriber failed")

    # ------------------------------------------------------------ replay

    def replay(self, after_id: int) -> tuple[list[SupportEvent], bool]:
        """(events after `after_id`, complete). Not complete means events were lost: reload the screen."""
        if after_id >= self._last_id:
            return [], True
        if not self._ring:
            return [], False
        complete = after_id >= self._ring[0].id - 1
        return [event for event in self._ring if event.id > after_id], complete

    # ------------------------------------------------------------ redis listener

    async def _listen(self) -> None:
        while True:
            pubsub = self._redis.pubsub()
            if pubsub is None:
                await asyncio.sleep(5)
                continue
            try:
                await pubsub.subscribe(CHANNEL)
                self._redis.mark_healthy()
                self._listening = True
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    try:
                        self.receive(SupportEvent.from_json(message["data"]))
                    except Exception:
                        logger.exception("Bad support event from Redis")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._redis.mark_failed(exc)
            finally:
                self._listening = False
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
            await asyncio.sleep(2)
