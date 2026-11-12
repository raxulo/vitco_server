from sqlalchemy import CheckConstraint
from sqlalchemy import Numeric
from decimal import Decimal
from sqlalchemy import func

from datetime import datetime
from uuid import UUID

from app.core.clock import now_naive_ist

from sqlalchemy import (
    ForeignKey,
    Index,
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
from app.core.database.types import NaiveDateTime


class AdvanceRecordModel(
    Base,
    UUIDMixin,
):
    __tablename__ = "advance_records"

    # =========================================================
    # USER
    #
    # Farmer / person jiske liye advance create hua
    # =========================================================

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # =========================================================
    # ADVANCE DATE
    # =========================================================

    advance_date: Mapped[datetime] = mapped_column(
        NaiveDateTime(),
        nullable=False,
    )

    # =========================================================
    # Total Amount
    # =========================================================

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20,scale=2),
        nullable=False,
    )

    # =========================================================
    # NOTES
    # =========================================================

    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    # =========================================================
    # CREATED BY
    #
    # Dairy / Admin / User jisne advance create kiya
    # =========================================================

    created_at: Mapped[datetime] = mapped_column(
        NaiveDateTime(),

        server_default=func.now(),
        # App-side IST time (the DB server default would be UTC on SQLite)
        default=now_naive_ist,

        nullable=False,

    )

    created_by: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # =========================================================
    # RELATIONSHIP
    #
    # One AdvanceRecord → Many AdvanceItems
    # =========================================================

    items: Mapped[list["AdvanceItemModel"]] = relationship(
        "AdvanceItemModel",
        back_populates="advance_record",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="noload",
    )

    # =========================================================
    # INDEXES
    # =========================================================

    __table_args__ = (

        Index(
            "ix_advance_record_user_date",
            "user_id",
            "advance_date",
        ),

        Index(
            "ix_advance_record_created_by_date",
            "created_by",
            "advance_date",
        ),

        Index(
            "ix_advance_record_date",
            "advance_date",
        ),
    )




class AdvanceItemModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "advance_record_items"

    # =========================================================
    # ADVANCE RECORD
    # =========================================================

    advance_record_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "advance_records.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # =========================================================
    # ITEM MASTER
    # =========================================================

    item_master_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "item_master.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # =========================================================
    # QUANTITY
    #
    # User manually enters quantity
    # =========================================================

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=20,
            scale=3,
        ),
        nullable=False,
    )

    # =========================================================
    # UNIT RATE
    #
    # ItemMaster ke current rate ka snapshot
    # =========================================================

    unit_rate: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=20,
            scale=2,
        ),
        nullable=False,
    )

    # =========================================================
    # AMOUNT
    #
    # quantity × unit_rate
    # =========================================================

    amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=20,
            scale=2,
        ),
        nullable=False,
    )

    # =========================================================
    # RELATIONSHIP
    # =========================================================

    advance_record: Mapped["AdvanceRecordModel"] = relationship(
        "AdvanceRecordModel",
        back_populates="items",
        lazy="noload",
    )

    # =========================================================
    # CONSTRAINTS + INDEXES
    # =========================================================

    __table_args__ = (

        CheckConstraint(
            "quantity > 0",
            name="ck_advance_item_quantity_positive",
        ),

        CheckConstraint(
            "unit_rate >= 0",
            name="ck_advance_item_unit_rate_non_negative",
        ),

        CheckConstraint(
            "amount >= 0",
            name="ck_advance_item_amount_non_negative",
        ),

        Index(
            "ix_advance_item_record",
            "advance_record_id",
        ),

        Index(
            "ix_advance_item_master",
            "item_master_id",
        ),

        Index(
            "ix_advance_item_record_master",
            "advance_record_id",
            "item_master_id",
        ),
    )