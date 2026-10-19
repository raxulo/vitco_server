"""
Item Master Database Model

Master entity for items/materials used within the system.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
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
from app.modules.masters.units.infrastructure.models import UnitMasterModel


class ItemMasterModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "item_master"

    # =========================================================
    # Item Identity
    # =========================================================

    item_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
    )

    item_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Unit
    # =========================================================

    unit_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "unit_master.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Rate
    # =========================================================

    rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
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

    # =========================================================
    # Constraints
    # =========================================================

    __table_args__ = (
        UniqueConstraint(
            "item_name",
            "unit_id",
            name="uq_item_name_unit",
        ),
    )