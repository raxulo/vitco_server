"""
Notification Enums

Python 3.13+
"""

from __future__ import annotations

from enum import StrEnum


class Platform(StrEnum):
    ANDROID = "android"
    IOS = "ios"


class NotificationStatus(StrEnum):
    """Life of one outbox row."""

    PENDING = "PENDING"      # waiting to be sent (or to be retried)
    SENDING = "SENDING"      # taken by a worker
    SENT = "SENT"            # reached at least one device
    FAILED = "FAILED"        # gave up after the last attempt
    SKIPPED = "SKIPPED"      # not sent on purpose (user online, no device, push disabled)
