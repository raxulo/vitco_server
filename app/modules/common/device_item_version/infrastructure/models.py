from __future__ import annotations

from enum import IntEnum
from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import UUIDMixin, TimestampMixin


class DeviceType(IntEnum):
    MCC = 1
    VLCC = 2


class DeviceItemVersion(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "device_item_versions"

    __table_args__ = (
        UniqueConstraint(
            "device_type",
            "device_id",
            "item_name",
            name="uq_device_item_version",
        ),
        Index(
            "ix_device_item_version_device",
            "device_id",
            "device_type",
        ),
    )

    device_type: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
    )

    device_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    item_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
