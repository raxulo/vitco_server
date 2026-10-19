"""
MCC Database Model

Milk Collection Center master entity.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import (
    AuditMixin,
    UUIDMixin,
    SoftDeleteMixin
)

from app.modules.mcc.domain.enums import (
    MccType,
)


class MccModel(
    Base,
    UUIDMixin,
    AuditMixin,
    SoftDeleteMixin,
):

    __tablename__ = "mcc_master"

    # =========================================================
    # Identity
    # =========================================================

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    code: Mapped[str] = mapped_column(
        "mcc_code",
        String(30),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    mcc_type: Mapped[MccType] = mapped_column(
        Enum(MccType),
        nullable=False,
        default=MccType.NORMAL,
    )

    # =========================================================
    # Route / Sampling
    # =========================================================

    route_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    sample_start: Mapped[int] = mapped_column(
        "sample_sequence_start",
        Integer,
        nullable=True,
        default=0,
    )

    sample_end: Mapped[int] = mapped_column(
        "sample_sequence_end",
        Integer,
        nullable=True,
        default=0,
    )

    # =========================================================
    # Common References
    # =========================================================

    address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("addresses.id"),
        nullable=True,
        index=True,
    )

    bank_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bank_accounts.id"),
        nullable=True,
        index=True,
    )

    fixed_rate_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("fixed_rate_configs.id"),
        nullable=True,
        index=True,
    )

    milk_quality_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("milk_quality_configs.id"),
        nullable=True,
        index=True,
    )

    settings_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "settings.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        unique=True,
        index=True,
    )



    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

