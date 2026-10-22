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
class CreateVlccCollectionCommand:

    vlcc_id: UUID
    farmer_id: UUID
    collected_at: datetime   
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None
    snf_percent: Decimal | None
    quantity: Decimal
    quantity_collection_mode: QuantityCollectionMode = QuantityCollectionMode.MANUAL
    measurement_mode: MeasurementMode = MeasurementMode.MANUAL
    rate_per_unit: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    payment_mode: PaymentMode = PaymentMode.CASH
    status: CollectionStatus = CollectionStatus.UNPAID
    rank: int | None = None
    calibration_fat: Decimal | None = None
    calibration_snf: Decimal | None = None


@dataclass(slots=True)
class UpdateVlccCollectionCommand:

    id: UUID
    vlcc_id: UUID
    farmer_id: UUID
    collected_at: datetime
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None
    snf_percent: Decimal | None
    quantity: Decimal
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode
    rate_per_unit: Decimal
    total_amount: Decimal
    payment_mode: PaymentMode
    status: CollectionStatus
    rank: int | None
    calibration_fat: Decimal | None
    calibration_snf: Decimal | None


@dataclass(slots=True)
class DeleteVlccCollectionCommand:

    id: UUID


@dataclass(slots=True)
class BulkDeleteVlccCollectionCommand:

    ids: list[UUID]



@dataclass(slots=True)
class GetVlccCollectionQuery:

    id: UUID


@dataclass(slots=True)
class ListVlccCollectionsQuery:

    page: int = 1
    size: int = 20
    # VLCC name, farmer name or farmer code
    keyword: str | None = None
    # collected_at range: from inclusive, to exclusive
    date_from: datetime | None = None
    date_to: datetime | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
