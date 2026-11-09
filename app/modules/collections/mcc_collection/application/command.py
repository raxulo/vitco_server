from app.modules.mcc.domain.enums import MccType

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
from app.modules.collections.mcc_collection.domain.listing import MccCollectionFilters
from app.modules.masters.advanced.domain.enums import PaymentMode


@dataclass(slots=True, kw_only=True)
class CreateMccCollectionCommand:

    mcc_id: UUID
    vlcc_id: UUID
    collected_at: datetime
    shift: CollectionShift
    fat_percent: Decimal = Decimal("0.00")
    snf_percent: Decimal = Decimal("0.00")
    clr_value: Decimal = Decimal("0.00")
    quantity: Decimal
    quantity_collection_mode: QuantityCollectionMode = QuantityCollectionMode.MANUAL
    measurement_mode: MeasurementMode = MeasurementMode.MANUAL
    rate_per_unit: Decimal = Decimal("0.0000")
    total_amount: Decimal = Decimal("0.00")
    payment_mode: PaymentMode = PaymentMode.CASH
    status: CollectionStatus = CollectionStatus.UNPAID
    sample_number: int = 0
    can_count: int = 0
    rank: int | None = None
    detection_value: Decimal | None = None
    calibration_fat: Decimal | None = None
    calibration_snf: Decimal | None = None
    milk_type: MilkType = MilkType.COW
    mcc_type: MccType = MccType.NORMAL



@dataclass(slots=True)
class UpdateMccCollectionCommand:

    id: UUID
    collection_number: str
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
    sample_number: int
    can_count: int
    rank: int | None
    detection_value: Decimal | None
    calibration_fat: Decimal | None
    calibration_snf: Decimal | None


@dataclass(slots=True)
class DeleteMccCollectionCommand:

    id: UUID


@dataclass(slots=True)
class BulkDeleteMccCollectionCommand:

    ids: list[UUID]



@dataclass(slots=True)
class GetMccCollectionQuery:

    id: UUID


@dataclass(slots=True)
class ListMccCollectionsQuery:

    page: int = 1
    size: int = 20
    # MCC name / code or VLCC name / code
    keyword: str | None = None
    # collected_at range: from inclusive, to exclusive
    date_from: datetime | None = None
    date_to: datetime | None = None
    filters: MccCollectionFilters | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(slots=True)
class GetNextSampleNumberQuery:

    mcc_id: UUID
    shift: CollectionShift
    collected_at: datetime


@dataclass(slots=True)
class GetCollectionBySampleNumberQuery:
    mcc_id: UUID
    sample_number: int
    shift: CollectionShift
    collected_at: datetime

