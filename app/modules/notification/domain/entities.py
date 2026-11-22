"""
Notification Entities

Pure dataclasses, no framework imports. The module knows nothing about tickets, payments or any
other feature: a notification only names its `source` module and an optional `reference_id`.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.notification.domain.enums import NotificationStatus


@dataclass(slots=True, kw_only=True)
class DeviceToken:
    """One app installation that can receive pushes; it belongs to the last user who registered it."""

    id: UUID
    user_id: UUID
    fcm_token: str
    platform: str
    app_version: str | None = None
    is_active: bool = True
    last_seen: datetime | None = None


@dataclass(slots=True, kw_only=True)
class Notification:
    """A push waiting in the outbox, written in the same transaction as the change it reports."""

    id: UUID
    user_id: UUID
    source: str                          # the module that asked for it, e.g. "support"
    type: str                            # the module's own kind, e.g. "REPLY"
    title: str
    body: str
    reference_id: str | None = None      # what the app should open, e.g. a ticket id
    data: dict[str, str] = field(default_factory=dict)
    skip_if_online: bool = False         # e.g. a chat reply the user already sees live
    status: NotificationStatus = NotificationStatus.PENDING
    attempts: int = 0
    next_attempt_at: datetime | None = None
    sent_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime | None = None

    @property
    def payload(self) -> dict[str, str]:
        """FCM data: strings only. `source`, `type` and `reference_id` always present for the app's router."""
        data = {key: str(value) for key, value in (self.data or {}).items()}
        data.update({"source": self.source, "type": self.type})
        if self.reference_id:
            data["reference_id"] = self.reference_id
        return data
