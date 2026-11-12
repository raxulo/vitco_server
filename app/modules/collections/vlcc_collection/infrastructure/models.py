"""
VLCC Milk Collection Persistence Model.

Represents one milk collection transaction recorded at a VLCC
for a farmer during a collection shift.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.clock import get_ist_now, now_naive_ist

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import TimestampMixin, UUIDMixin
from app.core.database.types import NaiveDateTime

from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    CollectionStatus,
    MeasurementMode,
    QuantityCollectionMode,
)
from app.modules.masters.advanced.domain.enums import PaymentMode
from app.modules.ratechart.domain.enums import MilkType


class VlccCollectionModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    """
    Persistent VLCC milk-collection transaction.

    Relationship:

        VLCC
          └── Farmer
                └── Collection
    """

    __tablename__ = "vlcc_collections"

    # =========================================================
    # Scope
    # =========================================================

    vlcc_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "vlcc_master.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    farmer_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "farmer_master.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # =========================================================
    # Collection Event
    # =========================================================

    collected_at: Mapped[datetime] = mapped_column(
        NaiveDateTime(),
        nullable=False,
        default=get_ist_now,
    )

    shift: Mapped[CollectionShift] = mapped_column(
        Enum(
            CollectionShift,
            name="vlcc_collection_shift_enum",
        ),
        nullable=False,
        default=CollectionShift.MORNING,
    )

    milk_type: Mapped[MilkType] = mapped_column(
        Enum(
            MilkType,
            name="vlcc_collection_milk_type_enum",
        ),
        nullable=False,
    )

    # =========================================================
    # Milk Quality
    # =========================================================

    fat_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 1),
        nullable=True,
    )

    snf_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 1),
        nullable=True,
    )

    # =========================================================
    # Quantity
    # =========================================================

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    quantity_collection_mode: Mapped[
        QuantityCollectionMode
    ] = mapped_column(
        Enum(
            QuantityCollectionMode,
            name="vlcc_quantity_collection_mode_enum",
        ),
        nullable=False,
        default=QuantityCollectionMode.MANUAL,
    )

    measurement_mode: Mapped[
        MeasurementMode
    ] = mapped_column(
        Enum(
            MeasurementMode,
            name="vlcc_measurement_mode_enum",
        ),
        nullable=False,
        default=MeasurementMode.MANUAL,
    )

    # =========================================================
    # Rate / Amount
    # =========================================================

    rate_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # =========================================================
    # Payment
    # =========================================================

    payment_mode: Mapped[PaymentMode] = mapped_column(
        Enum(
            PaymentMode,
            name="vlcc_collection_payment_mode_enum",
        ),
        nullable=False,
        default=PaymentMode.CASH,
    )

    status: Mapped[CollectionStatus] = mapped_column(
        Enum(
            CollectionStatus,
            name="vlcc_collection_status_enum",
        ),
        nullable=False,
        default=CollectionStatus.UNPAID,
    )

    # =========================================================
    # Collection Metadata
    # =========================================================

    rank: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # =========================================================
    # Analyzer Calibration
    # =========================================================

    calibration_fat: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3),
        nullable=True,
    )

    calibration_snf: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3),
        nullable=True,
    )

    # =========================================================
    # Soft Delete
    # =========================================================

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # =========================================================
    # Query / Reporting Indexes
    # =========================================================

    __table_args__ = (

        # Farmer history:
        # WHERE farmer_id = ? AND collected_at BETWEEN ? AND ?
        Index(
            "ix_vlcc_collections_farmer_collected",
            "farmer_id",
            "collected_at",
        ),

        # VLCC date-wise reports
        Index(
            "ix_vlcc_collections_vlcc_collected",
            "vlcc_id",
            "collected_at",
        ),

        # VLCC shift reports
        Index(
            "ix_vlcc_collections_vlcc_collected_shift",
            "vlcc_id",
            "collected_at",
            "shift",
        ),

        # VLCC + milk type reports
        Index(
            "ix_vlcc_collections_vlcc_milk_type_collected",
            "vlcc_id",
            "milk_type",
            "collected_at",
        ),

        # Payment/status reports
        Index(
            "ix_vlcc_collections_vlcc_status_collected",
            "vlcc_id",
            "status",
            "collected_at",
        ),

        # Soft-delete aware reporting
        Index(
            "ix_vlcc_collections_vlcc_deleted_collected",
            "vlcc_id",
            "is_deleted",
            "collected_at",
        ),
    )



class DispatchModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "dispatches"

    vlcc_id: Mapped[UUID] = mapped_column(
        ForeignKey("vlcc_master.id", ondelete="RESTRICT"),
        nullable=False,
    )

    collected_at: Mapped[datetime] = mapped_column(
        NaiveDateTime(),
        nullable=False,
        default=now_naive_ist,
    )

    shift: Mapped[CollectionShift] = mapped_column(
        Enum(
            CollectionShift,
            name="dispatch_shift_enum",
        ),
        nullable=False,
        default=CollectionShift.MORNING,
    )

    fat_percent: Mapped[Decimal] = mapped_column(
        Numeric(3, 1),
        nullable=False,
        default=Decimal("0.0"),
    )

    snf_percent: Mapped[Decimal] = mapped_column(
        Numeric(3, 1),
        nullable=False,
        default=Decimal("0.0"),
    )

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    can_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    quantity_collection_mode: Mapped[
        QuantityCollectionMode
    ] = mapped_column(
        Enum(
            QuantityCollectionMode,
            name="dispatch_quantity_collection_mode_enum",
        ),
        nullable=False,
        default=QuantityCollectionMode.MANUAL,
    )

    measurement_mode: Mapped[
        MeasurementMode
    ] = mapped_column(
        Enum(
            MeasurementMode,
            name="dispatch_measurement_mode_enum",
        ),
        nullable=False,
        default=MeasurementMode.MANUAL,
    )

    __table_args__ = (
        Index(
            "ix_dispatches_vlcc_collected_at",
            "vlcc_id",
            "collected_at",
        ),
    )