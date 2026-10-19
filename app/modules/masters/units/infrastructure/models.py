"""
Unit Master Database Model

Master entity for measurement/business units.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)


class UnitMasterModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "unit_master"

    # =========================================================
    # Unit Identity
    # =========================================================

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
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