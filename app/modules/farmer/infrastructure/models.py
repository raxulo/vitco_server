"""
Farmer Database Model

Farmer master entity representing a milk supplier.
"""

from app.core.database.mixins import AuditMixin
from sqlalchemy import UniqueConstraint
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
    TimestampMixin,
    UUIDMixin,
    SoftDeleteMixin,
)

from app.modules.farmer.domain.enums import (
    MilkType,
)


class FarmerModel(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):

    __tablename__ = "farmer_master"

    __table_args__ = (
        UniqueConstraint(
            "vlcc_id",
            "farmer_code",
            name="uq_farmer_vlcc_code",
        ),
    )

    # =========================================================
    # Identity / Authentication
    # =========================================================

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
        index=True,
        onupdate=None
    )

    farmer_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Collection Hierarchy
    # =========================================================

    vlcc_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("vlcc_master.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Address
    # =========================================================

    address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("addresses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Bank Account
    # =========================================================

    bank_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bank_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Milk
    # =========================================================

    milk_type: Mapped[MilkType] = mapped_column(
        Enum(MilkType),
        nullable=False,
        default=MilkType.MIXED,
    )

    # =========================================================
    # Rate Configuration
    # =========================================================

    assigned_chart_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )



    # =========================================================
    # Communication
    # =========================================================

    sms_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # =========================================================
    # Status
    # =========================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # =========================================================
    # Audit
    # =========================================================

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )