"""
Route Master Database Model

Master entity for milk collection/distribution routes.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    Integer,
    String,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)


class RouteMasterModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "route_master"

    # =========================================================
    # Route Identity
    # =========================================================

    route_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )

    route_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Status
    # =========================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # =========================================================
    # Audit
    # =========================================================

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )