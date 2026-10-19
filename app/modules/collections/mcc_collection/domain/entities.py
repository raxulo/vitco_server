from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MilkType,
    QuantityCollectionMode,
    MeasurementMode,
    CollectionStatus,
)
from app.modules.masters.advanced.domain.enums import PaymentMode


@dataclass(slots=True)
class MccCollection:

    id: UUID
    mcc_id: UUID
    vlcc_id: UUID
    collected_at: datetime
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None
    snf_percent: Decimal | None
    clr_value: Decimal | None
    quantity: Decimal
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode
    rate_per_unit: Decimal
    total_amount: Decimal
    payment_mode: PaymentMode
    status: CollectionStatus
    rank: int | None
    sample_number: int
    detection_value: Decimal | None
    calibration_fat: Decimal | None
    calibration_snf: Decimal | None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime | None
    can_count: int = 0
