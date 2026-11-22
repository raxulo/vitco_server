"""
Notification Repository Interface

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.notification.domain.entities import DeviceToken, Notification
from app.modules.notification.domain.enums import NotificationStatus


class INotificationRepository(ABC):
    """Device tokens and the push outbox. Never commits: the caller owns the transaction."""

    # ---------------------------------------------------- device tokens

    @abstractmethod
    async def upsert_token(self, *, user_id: UUID, fcm_token: str, platform: str, app_version: str | None) -> DeviceToken: ...

    @abstractmethod
    async def remove_token(self, *, user_id: UUID, fcm_token: str) -> bool: ...

    @abstractmethod
    async def active_tokens(self, user_id: UUID) -> list[DeviceToken]: ...

    @abstractmethod
    async def deactivate_tokens(self, tokens: list[str]) -> None: ...

    # ---------------------------------------------------- outbox

    @abstractmethod
    async def add(self, notification: Notification) -> None: ...

    @abstractmethod
    async def claim_due(self, *, now: datetime, limit: int) -> list[Notification]: ...

    @abstractmethod
    async def finish(
        self,
        notification_id: UUID,
        *,
        status: NotificationStatus,
        attempts: int,
        next_attempt_at: datetime | None = None,
        sent_at: datetime | None = None,
        error: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def release_stuck(self, *, before: datetime) -> int: ...

    @abstractmethod
    async def purge_finished(self, *, before: datetime) -> int: ...

    @abstractmethod
    async def list_for_user(self, user_id: UUID, *, source: str | None = None) -> list[Notification]: ...
