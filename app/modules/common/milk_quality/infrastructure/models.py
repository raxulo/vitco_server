from __future__ import annotations

from uuid import UUID

from sqlalchemy import Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import UUIDMixin


class MilkQualityConfigModel(
    Base,
    UUIDMixin,
):

    __tablename__ = "milk_quality_configs"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    # =========================================================
    # Cow
    # =========================================================

    cow_min_fat: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    cow_max_fat: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    cow_min_snf: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    cow_max_snf: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    # =========================================================
    # Buffalo
    # =========================================================

    buffalo_min_fat: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    buffalo_max_fat: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    buffalo_min_snf: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )

    buffalo_max_snf: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )