"""
Notification Models (SQLAlchemy 2.0, migration 0007)

Shared by every module: `notification_device_tokens` and `notification_outbox`. No foreign key to any
feature table; a row names its `source` module and an optional `reference_id` instead.

Python 3.13+
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_naive_ist
from app.core.database.base import Base
from app.core.database.mixins import UUIDMixin
from app.core.database.types import NaiveDateTime


class NotificationDeviceTokenModel(Base, UUIDMixin):

    __tablename__ = "notification_device_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    fcm_token: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_seen: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)
    created_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)


class NotificationOutboxModel(Base, UUIDMixin):

    __tablename__ = "notification_outbox"
    __table_args__ = (
        Index("ix_notification_outbox_status_next", "status", "next_attempt_at"),
        Index("ix_notification_outbox_source_reference", "source", "reference_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    skip_if_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)
    sent_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)
