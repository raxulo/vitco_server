"""
Fixed Rate Configuration Database Model
"""

from __future__ import annotations
from uuid import UUID
from sqlalchemy import Float, ForeignKey
from sqlalchemy.orm import Mapped,mapped_column
from app.core.database.base import Base
from app.core.database.mixins import UUIDMixin


class FixedRateConfigModel(
    Base,
    UUIDMixin,
):

    __tablename__ = "fixed_rate_configs"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # =========================================================
    # Fixed Rate
    # =========================================================

    fixed_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )

    less_detection: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )

    high_detection: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )

    # =========================================================
    # FAT Limits
    # =========================================================

    min_fat: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )

    max_fat: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )

    # =========================================================
    # SNF Limits
    # =========================================================

    min_snf: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )

    max_snf: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=True,
    )