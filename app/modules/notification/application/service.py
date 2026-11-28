"""
Notification Service: the one way any module asks for a push (DECISION-033)

    await notifications.notify(
        user_id=..., source="payments", type="PAYMENT_RECEIVED",
        title="Payment received", body="₹ 2,450 for 1-15 Nov", reference_id=str(payment.id),
    )

Call it inside the transaction of the change being reported: the outbox row commits or rolls back with
it, so a push is never sent for work that did not happen and a failed push never loses the work. The
push worker sends the row afterwards.

With push disabled (no Firebase credential) nothing is written: rows nobody will send would only grow
the table, and on SQLite a worker marking them would compete with requests for the write lock.

Python 3.13+
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from app.modules.notification.domain.entities import Notification
from app.modules.notification.domain.exceptions import NotificationValidationException
from app.modules.notification.domain.irepository import INotificationRepository

_SOURCE = re.compile(r"^[a-z][a-z0-9_]{1,29}$")
TITLE_LIMIT = 120
BODY_LIMIT = 180


def cut(text: str | None, limit: int) -> str:
    """One line, at most `limit` characters, ending with … when shortened."""
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class NotificationService:

    __slots__ = ("_repository", "_enabled")

    def __init__(self, repository: INotificationRepository, *, enabled: bool = True) -> None:
        self._repository = repository
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def notify(
        self,
        *,
        user_id: UUID,
        source: str,
        type: str,
        title: str,
        body: str,
        reference_id: str | None = None,
        data: dict[str, str] | None = None,
        skip_if_online: bool = False,
    ) -> Notification | None:
        """Queue a push for one user in the caller's transaction. Returns None while push is disabled.

        `source` names the calling module (lowercase), `type` its own kind of message. `data` is extra
        string values for the app; `source`, `type` and `reference_id` are always added to it.
        `skip_if_online` drops the push when the user has the app open (for chat-like messages).
        """
        if not _SOURCE.match(source or ""):
            raise NotificationValidationException("Notification source must be a short lowercase module name.")
        if not (type or "").strip():
            raise NotificationValidationException("Notification type is required.")
        if not self._enabled:
            return None
        notification = Notification(
            id=uuid4(),
            user_id=user_id,
            source=source,
            type=type.strip()[:40],
            title=cut(title, TITLE_LIMIT) or "Notification",
            body=cut(body, BODY_LIMIT),
            reference_id=(str(reference_id)[:64] if reference_id else None),
            data={str(key): str(value) for key, value in (data or {}).items()},
            skip_if_online=skip_if_online,
        )
        await self._repository.add(notification)
        return notification

    async def notify_many(self, user_ids: list[UUID], **message) -> int:
        """The same push for several users (e.g. everyone under a VLCC). Returns how many were queued."""
        queued = 0
        for user_id in dict.fromkeys(user_ids):
            if await self.notify(user_id=user_id, **message) is not None:
                queued += 1
        return queued
