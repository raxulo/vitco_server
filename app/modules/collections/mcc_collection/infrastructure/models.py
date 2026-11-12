from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.core.clock import get_ist_now

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.ext.hybrid import hybrid_property
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


class MccCollectionModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    """
    Persistent MCC milk-collection transaction.

    One row represents one milk collection event
    recorded at an MCC for a VLCC.
    """

    __tablename__ = "mcc_collections"

    # =========================================================
    # Ownership / Scope
    # =========================================================

    mcc_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "mcc_master.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    vlcc_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "vlcc_master.id",
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
        default=get_ist_now
    )

    shift: Mapped[CollectionShift] = mapped_column(
        Enum(
            CollectionShift,
            name="collection_shift_enum",
        ),
        nullable=False,
    )

    milk_type: Mapped[MilkType] = mapped_column(
        Enum(
            MilkType,
            name="collection_milk_type_enum",
        ),
        nullable=False,
        default=MilkType.MIXED,
    )

    # =========================================================
    # Milk Quality
    # =========================================================

    fat_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3),
        nullable=True,
    )

    snf_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 3),
        nullable=True,
    )

    clr_value: Mapped[Decimal | None] = mapped_column(
        Numeric(8, 3),
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

    quantity_collection_mode: Mapped[QuantityCollectionMode] = mapped_column(
        Enum(
            QuantityCollectionMode,
            name="quantity_collection_mode_enum",
        ),
        nullable=False,
        default=QuantityCollectionMode.MANUAL,
    )

    measurement_mode: Mapped[MeasurementMode] = mapped_column(
        Enum(
            MeasurementMode,
            name="measurement_mode_enum",
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
            name="collection_payment_mode_enum",
        ),
        nullable=False,
        default=PaymentMode.CASH,
    )

    status: Mapped[CollectionStatus] = mapped_column(
        Enum(
            CollectionStatus,
            name="collection_status_enum",
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

    sample_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    can_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    detection_value: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 3),
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

    @hybrid_property
    def collection_date(self):
        return self.collected_at.date()

    @collection_date.expression
    def collection_date(cls):
        return func.date(cls.collected_at)

    # =========================================================
    # Reporting Indexes
    # =========================================================

    __table_args__ = (

        # MCC + date/time + shift
        Index(
            "ix_mcc_collections_mcc_collected_shift",
            "mcc_id",
            "collected_at",
            "shift",
        ),

        # MCC + milk type + date/time
        Index(
            "ix_mcc_collections_mcc_milk_type_collected",
            "mcc_id",
            "milk_type",
            "collected_at",
        ),

        # VLCC + date/time + shift
        Index(
            "ix_mcc_collections_vlcc_collected_shift",
            "vlcc_id",
            "collected_at",
            "shift",
        ),

        # Payment/status reports
        Index(
            "ix_mcc_collections_mcc_status_collected",
            "mcc_id",
            "status",
            "collected_at",
        ),

        # Soft-delete filtering
        Index(
            "ix_mcc_collections_mcc_deleted_collected",
            "mcc_id",
            "is_deleted",
            "collected_at",
        ),
    )