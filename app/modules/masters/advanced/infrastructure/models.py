"""
Advance Database Models

Contains:
    - AdvanceMasterModel
    - AdvanceItemModel
    - AdvancePaymentModel

An advance can contain multiple items and multiple partial payments.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)

from app.modules.masters.advanced.domain.enums import (
    AdvanceStatus,
    PaymentMode,
)


# =============================================================
# Advance Master
# =============================================================


class AdvanceMasterModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    """
    Represents an advance transaction issued to a user.

    One advance can contain:
        - Multiple items
        - Multiple partial payments
    """

    __tablename__ = "advance_master"

    # =========================================================
    # Identity
    # =========================================================

    advance_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    # =========================================================
    # Transaction
    # =========================================================

    advance_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # =========================================================
    # Selected User
    # =========================================================

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Amount Summary
    # =========================================================

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    paid_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    outstanding_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # =========================================================
    # Status
    # =========================================================

    status: Mapped[AdvanceStatus] = mapped_column(
        Enum(
            AdvanceStatus,
            name="advance_status_enum",
        ),
        nullable=False,
        default=AdvanceStatus.UNPAID,
        index=True,
    )

    # =========================================================
    # Notes
    # =========================================================

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =========================================================
    # Status / Soft Delete
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
    # Relationships
    # =========================================================

    items: Mapped[list["AdvancePayItemModel"]] = relationship(
        "AdvancePayItemModel",
        back_populates="advance",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    payments: Mapped[list["AdvancePaymentModel"]] = relationship(
        "AdvancePaymentModel",
        back_populates="advance",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AdvancePaymentModel.payment_date",
    )

    # =========================================================
    # Constraints / Indexes
    # =========================================================

    __table_args__ = (
        CheckConstraint(
            "total_amount >= 0",
            name="ck_advance_total_amount",
        ),
        CheckConstraint(
            "paid_amount >= 0",
            name="ck_advance_paid_amount",
        ),
        CheckConstraint(
            "outstanding_amount >= 0",
            name="ck_advance_outstanding_amount",
        ),
        CheckConstraint(
            "paid_amount <= total_amount",
            name="ck_advance_paid_not_greater_than_total",
        ),
        Index(
            "ix_advance_user_date",
            "user_id",
            "advance_date",
        ),
        Index(
            "ix_advance_user_status",
            "user_id",
            "status",
        ),
    )


# =============================================================
# Advance Items
# =============================================================


class AdvancePayItemModel(
    Base,
    UUIDMixin,
):
    """
    Individual item included in an advance.

    One AdvanceMaster can have multiple AdvanceItem records.
    """

    __tablename__ = "advance_items"

    # =========================================================
    # Advance
    # =========================================================

    advance_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "advance_master.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Item
    # =========================================================

    item_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "item_master.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Item Snapshot
    # =========================================================

    item_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    # =========================================================
    # Quantity
    # =========================================================

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3),
        nullable=False,
    )

    # =========================================================
    # Rate Snapshot
    # =========================================================

    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(12, 4),
        nullable=False,
    )

    # =========================================================
    # Total
    # =========================================================

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    # =========================================================
    # Relationships
    # =========================================================

    advance: Mapped["AdvanceMasterModel"] = relationship(
        "AdvanceMasterModel",
        back_populates="items",
    )

    # =========================================================
    # Constraints
    # =========================================================

    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_advance_item_quantity_positive",
        ),
        CheckConstraint(
            "unit_rate >= 0",
            name="ck_advance_item_rate_non_negative",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_advance_item_total_non_negative",
        ),
        Index(
            "ix_advance_item_lookup",
            "advance_id",
            "item_id",
        ),
    )


# =============================================================
# Advance Payments
# =============================================================


class AdvancePaymentModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    """
    Represents an individual payment against an advance.

    Multiple partial payments are supported.
    """

    __tablename__ = "advance_payments"

    # =========================================================
    # Advance
    # =========================================================

    advance_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "advance_master.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Payment Date
    # =========================================================

    payment_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # =========================================================
    # Payment Amount
    # =========================================================

    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    # =========================================================
    # Payment Mode
    # =========================================================

    payment_mode: Mapped[PaymentMode] = mapped_column(
        Enum(
            PaymentMode,
            name="advance_payment_mode_enum",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Payment Reference
    # =========================================================

    reference_number: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Notes
    # =========================================================

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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
    # Relationships
    # =========================================================

    advance: Mapped["AdvanceMasterModel"] = relationship(
        "AdvanceMasterModel",
        back_populates="payments",
    )

    # =========================================================
    # Constraints
    # =========================================================

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_advance_payment_amount_positive",
        ),
        Index(
            "ix_advance_payment_advance_date",
            "advance_id",
            "payment_date",
        ),
    )