"""
Push Worker (REQ-77, DECISION-033)

A small asyncio task inside the API process (push volume is low; CON-08). Every few seconds it claims
due outbox rows in a short transaction of its own, then sends them outside any transaction:

- `skip_if_online` and the user has the app open (any registered presence check says so): SKIPPED;
- no active device: SKIPPED;
- sender disabled (no Firebase credential): SKIPPED with the reason;
- sent to at least one device: SENT; tokens FCM reports as dead are switched off;
- only temporary failures: tried again with growing delays, FAILED after 5 attempts.

It does not know any feature module. Modules that know when a user is "online" (the support sockets
today) add a presence check with `add_presence`.

It runs in a fresh context so it never shares a database session with a request.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import contextvars
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from uuid import UUID

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.notification.application.sender import PushSender
from app.modules.notification.domain.entities import Notification
from app.modules.notification.domain.enums import NotificationStatus
from app.modules.notification.domain.irepository import INotificationRepository

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BATCH = 20
STUCK_AFTER = timedelta(minutes=5)
KEEP_FOR = timedelta(days=30)

PresenceCheck = Callable[[UUID], Awaitable[bool]]


def backoff(attempts: int) -> timedelta:
    """30 s, 1 min, 2 min, 4 min, ... at most 30 min."""
    return timedelta(seconds=min(1800, 30 * 2 ** max(0, attempts - 1)))


class PushWorker:

    __slots__ = ("_database", "_repository", "_sender", "_presence", "_interval", "_task", "_last_purge")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: INotificationRepository,
        sender: PushSender,
        interval: float = 3.0,
    ) -> None:
        self._database = database
        self._repository = repository
        self._sender = sender
        self._presence: list[PresenceCheck] = []
        self._interval = max(0.5, interval)
        self._task: asyncio.Task | None = None
        self._last_purge = 0.0

    @property
    def sender(self) -> PushSender:
        return self._sender

    def add_presence(self, check: PresenceCheck) -> None:
        """A module that can tell whether a user has the app open right now."""
        self._presence.append(check)

    async def _online(self, user_id: UUID) -> bool:
        for check in self._presence:
            try:
                if await check(user_id):
                    return True
            except Exception:
                logger.warning("A presence check failed; treating the user as offline")
        return False

    async def start(self) -> None:
        """Runs only with a working sender; without a Firebase credential there is nothing to send."""
        if not self._sender.enabled:
            logger.info("Push worker not started: push notifications are disabled.")
            return
        if self._task is None:
            async with self._database.transaction():
                released = await self._repository.release_stuck(before=now_naive_ist() - STUCK_AFTER)
            if released:
                logger.info("Push worker released %s notifications left half sent", released)
            self._task = asyncio.create_task(self._loop(), name="push-worker", context=contextvars.Context())

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await self._sender.close()

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                while await self.run_once():
                    pass                                   # keep going while there is a backlog
                if loop.time() - self._last_purge > 3600:
                    self._last_purge = loop.time()
                    async with self._database.transaction():
                        await self._repository.purge_finished(before=now_naive_ist() - KEEP_FOR)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Push worker round failed; trying again shortly")
            await asyncio.sleep(self._interval)

    async def run_once(self) -> int:
        """One batch; returns how many notifications were handled."""
        async with self._database.transaction():
            batch = await self._repository.claim_due(now=now_naive_ist(), limit=BATCH)
        for notification in batch:
            await self._deliver(notification)
        return len(batch)

    async def _deliver(self, notification: Notification) -> None:
        attempts = notification.attempts + 1
        if not self._sender.enabled:
            await self._finish(notification.id, NotificationStatus.SKIPPED, attempts, error="push disabled")
            return
        if notification.skip_if_online and await self._online(notification.user_id):
            await self._finish(notification.id, NotificationStatus.SKIPPED, attempts, error="user online")
            return
        async with self._database.transaction():
            tokens = await self._repository.active_tokens(notification.user_id)
        if not tokens:
            await self._finish(notification.id, NotificationStatus.SKIPPED, attempts, error="no device")
            return

        sent, dead, retry, last_error = 0, [], False, ""
        for token in tokens:
            result = await self._sender.send(
                token.fcm_token, title=notification.title, body=notification.body, data=notification.payload,
            )
            if result.ok:
                sent += 1
            elif result.unregistered:
                dead.append(token.fcm_token)
            else:
                retry = retry or result.retryable
                last_error = result.error
        if dead:
            async with self._database.transaction():
                await self._repository.deactivate_tokens(dead)

        if sent:
            await self._finish(notification.id, NotificationStatus.SENT, attempts, sent_at=now_naive_ist())
        elif retry and attempts < MAX_ATTEMPTS:
            await self._finish(
                notification.id, NotificationStatus.PENDING, attempts,
                next_attempt_at=now_naive_ist() + backoff(attempts), error=last_error,
            )
        elif dead and len(dead) == len(tokens):
            await self._finish(notification.id, NotificationStatus.SKIPPED, attempts, error="no live device")
        else:
            await self._finish(notification.id, NotificationStatus.FAILED, attempts, error=last_error or "not sent")

    async def _finish(self, notification_id: UUID, status: NotificationStatus, attempts: int, **values) -> None:
        async with self._database.transaction():
            await self._repository.finish(notification_id, status=status, attempts=attempts, **values)
