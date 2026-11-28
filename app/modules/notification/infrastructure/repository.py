"""
Notification Repository

Async SQLAlchemy implementation of `INotificationRepository`. It never commits.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.notification.domain.entities import DeviceToken, Notification
from app.modules.notification.domain.enums import NotificationStatus
from app.modules.notification.domain.irepository import INotificationRepository
from app.modules.notification.infrastructure.models import NotificationDeviceTokenModel, NotificationOutboxModel

_FINISHED = (NotificationStatus.SENT.value, NotificationStatus.SKIPPED.value, NotificationStatus.FAILED.value)


class NotificationRepository(INotificationRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # ------------------------------------------------------------ device tokens

    async def upsert_token(self, *, user_id: UUID, fcm_token: str, platform: str, app_version: str | None) -> DeviceToken:
        """One row per token; registering it again (even as another user, e.g. a shared phone) moves it."""
        model = await self._session.scalar(
            select(NotificationDeviceTokenModel).where(NotificationDeviceTokenModel.fcm_token == fcm_token)
        )
        now = now_naive_ist()
        if model is None:
            model = NotificationDeviceTokenModel(
                user_id=user_id, fcm_token=fcm_token, platform=platform, app_version=app_version,
                is_active=True, last_seen=now,
            )
            self._session.add(model)
        else:
            model.user_id = user_id
            model.platform = platform
            model.app_version = app_version
            model.is_active = True
            model.last_seen = now
        await self._session.flush()
        return self._to_token(model)

    async def remove_token(self, *, user_id: UUID, fcm_token: str) -> bool:
        result = await self._session.execute(
            delete(NotificationDeviceTokenModel).where(
                NotificationDeviceTokenModel.fcm_token == fcm_token, NotificationDeviceTokenModel.user_id == user_id,
            )
        )
        return bool(result.rowcount)

    async def active_tokens(self, user_id: UUID) -> list[DeviceToken]:
        rows = await self._session.scalars(
            select(NotificationDeviceTokenModel)
            .where(NotificationDeviceTokenModel.user_id == user_id, NotificationDeviceTokenModel.is_active.is_(True))
            .order_by(NotificationDeviceTokenModel.last_seen.desc())
            .limit(10)
        )
        return [self._to_token(row) for row in rows]

    async def deactivate_tokens(self, tokens: list[str]) -> None:
        if tokens:
            await self._session.execute(
                update(NotificationDeviceTokenModel)
                .where(NotificationDeviceTokenModel.fcm_token.in_(tokens))
                .values(is_active=False)
                .execution_options(synchronize_session=False)
            )

    @staticmethod
    def _to_token(model: NotificationDeviceTokenModel) -> DeviceToken:
        return DeviceToken(
            id=model.id, user_id=model.user_id, fcm_token=model.fcm_token, platform=model.platform,
            app_version=model.app_version, is_active=model.is_active, last_seen=model.last_seen,
        )

    # ------------------------------------------------------------ outbox

    async def add(self, notification: Notification) -> None:
        self._session.add(
            NotificationOutboxModel(
                id=notification.id, user_id=notification.user_id, source=notification.source,
                type=notification.type, reference_id=notification.reference_id, title=notification.title,
                body=notification.body, data=notification.data, skip_if_online=notification.skip_if_online,
                status=NotificationStatus.PENDING.value, attempts=0, next_attempt_at=now_naive_ist(),
            )
        )
        await self._session.flush()

    async def claim_due(self, *, now: datetime, limit: int) -> list[Notification]:
        """Due PENDING rows, each switched to SENDING by a guarded update so two workers never take the same one.

        A SENDING row's `next_attempt_at` is the moment it was claimed, so `release_stuck` only frees rows
        whose worker stopped long ago, never one another process is sending right now.
        """
        ids = list(
            await self._session.scalars(
                select(NotificationOutboxModel.id)
                .where(
                    NotificationOutboxModel.status == NotificationStatus.PENDING.value,
                    NotificationOutboxModel.next_attempt_at <= now,
                )
                .order_by(NotificationOutboxModel.next_attempt_at, NotificationOutboxModel.id)
                .limit(limit)
            )
        )
        claimed: list[UUID] = []
        for notification_id in ids:
            result = await self._session.execute(
                update(NotificationOutboxModel)
                .where(
                    NotificationOutboxModel.id == notification_id,
                    NotificationOutboxModel.status == NotificationStatus.PENDING.value,
                )
                .values(status=NotificationStatus.SENDING.value, next_attempt_at=now)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount:
                claimed.append(notification_id)
        if not claimed:
            return []
        rows = await self._session.scalars(select(NotificationOutboxModel).where(NotificationOutboxModel.id.in_(claimed)))
        return [self._to_notification(row) for row in rows]

    async def finish(
        self,
        notification_id: UUID,
        *,
        status: NotificationStatus,
        attempts: int,
        next_attempt_at: datetime | None = None,
        sent_at: datetime | None = None,
        error: str | None = None,
    ) -> None:
        values: dict = {"status": status.value, "attempts": attempts, "last_error": error[:255] if error else None}
        if next_attempt_at is not None:
            values["next_attempt_at"] = next_attempt_at
        if sent_at is not None:
            values["sent_at"] = sent_at
        await self._session.execute(
            update(NotificationOutboxModel)
            .where(NotificationOutboxModel.id == notification_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    async def release_stuck(self, *, before: datetime) -> int:
        """SENDING rows claimed before `before` (their worker crashed or stopped) go back to PENDING."""
        result = await self._session.execute(
            update(NotificationOutboxModel)
            .where(
                NotificationOutboxModel.status == NotificationStatus.SENDING.value,
                NotificationOutboxModel.next_attempt_at < before,
            )
            .values(status=NotificationStatus.PENDING.value)
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)

    async def purge_finished(self, *, before: datetime) -> int:
        result = await self._session.execute(
            delete(NotificationOutboxModel).where(
                NotificationOutboxModel.status.in_(_FINISHED), NotificationOutboxModel.created_at < before,
            )
        )
        return int(result.rowcount or 0)

    async def list_for_user(self, user_id: UUID, *, source: str | None = None) -> list[Notification]:
        stmt = select(NotificationOutboxModel).where(NotificationOutboxModel.user_id == user_id)
        if source:
            stmt = stmt.where(NotificationOutboxModel.source == source)
        rows = await self._session.scalars(stmt.order_by(NotificationOutboxModel.created_at, NotificationOutboxModel.id))
        return [self._to_notification(row) for row in rows]

    @staticmethod
    def _to_notification(model: NotificationOutboxModel) -> Notification:
        return Notification(
            id=model.id, user_id=model.user_id, source=model.source, type=model.type,
            reference_id=model.reference_id, title=model.title, body=model.body, data=model.data or {},
            skip_if_online=model.skip_if_online, status=NotificationStatus(model.status), attempts=model.attempts,
            next_attempt_at=model.next_attempt_at, sent_at=model.sent_at, last_error=model.last_error,
            created_at=model.created_at,
        )
