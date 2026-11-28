"""
Device Handler (REQ-76): the app registers and removes its FCM tokens

Any signed-in app user may register a device; which pushes it then gets is up to the modules that
call `NotificationService`. One token belongs to one user (the last who registered it), a user may
have several devices.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.notification.domain.entities import DeviceToken, Notification
from app.modules.notification.domain.enums import Platform
from app.modules.notification.domain.exceptions import (
    DeviceRegistrationDeniedException,
    NotificationValidationException,
)
from app.modules.notification.domain.irepository import INotificationRepository


@dataclass(slots=True, kw_only=True)
class RegisterDeviceCommand:
    fcm_token: str
    platform: str
    app_version: str | None = None


class DeviceHandler:

    __slots__ = ("_database", "_repository")

    def __init__(self, *, database: DatabaseManager, repository: INotificationRepository) -> None:
        self._database = database
        self._repository = repository

    @staticmethod
    def _user(actor: CurrentUser | None) -> UUID:
        if actor is None:
            raise DeviceRegistrationDeniedException()
        return actor.id

    async def register(self, command: RegisterDeviceCommand, actor: CurrentUser | None) -> DeviceToken:
        token = (command.fcm_token or "").strip()
        platform = (command.platform or "").strip().lower()
        if not 20 <= len(token) <= 512 or any(ch.isspace() for ch in token):
            raise NotificationValidationException("This is not a valid device token.")
        if platform not in {item.value for item in Platform}:
            raise NotificationValidationException("Platform must be android or ios.")
        app_version = (command.app_version or "").strip()[:30] or None
        user_id = self._user(actor)
        async with self._database.transaction():
            return await self._repository.upsert_token(
                user_id=user_id, fcm_token=token, platform=platform, app_version=app_version,
            )

    async def remove(self, fcm_token: str, actor: CurrentUser | None) -> bool:
        """On logout. Removing a token that is not (or no longer) this user's does nothing."""
        user_id = self._user(actor)
        async with self._database.transaction():
            return await self._repository.remove_token(user_id=user_id, fcm_token=(fcm_token or "").strip())

    async def outbox_for(self, user_id: UUID, *, source: str | None = None) -> list[Notification]:
        """What was queued for a user (tests and support diagnostics)."""
        async with self._database.transaction():
            return await self._repository.list_for_user(user_id, source=source)
