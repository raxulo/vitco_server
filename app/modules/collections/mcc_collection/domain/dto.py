from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.administration.domain.enums import Role
from app.modules.mcc.domain.enums import MccType
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MilkType,
    QuantityCollectionMode,
    MeasurementMode,
    CollectionStatus,
)
from app.modules.masters.advanced.domain.enums import PaymentMode



@dataclass(slots=True)
class MccCollectionDto:

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
    sample_number: int
    can_count: int


@dataclass(slots=True, frozen=True, kw_only=True)
class MccCollectionListDto:

    id: UUID
    mcc_id: UUID
    vlcc_id: UUID
    collected_at: datetime
    shift: CollectionShift
    milk_type: MilkType
    quantity: Decimal
    total_amount: Decimal
    status: CollectionStatus
    fat_percent: Decimal | None
    snf_percent: Decimal | None
    clr_value: Decimal | None
    sample_number: int
    can_count: int
    rate_per_unit: Decimal
    payment_mode: PaymentMode
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode
    mcc_name: str
    mcc_code: str
    vlcc_name: str
    vlcc_uic_code: str
    is_deleted: bool = False



@dataclass(slots=True, kw_only=True)
class MccCollectionResult:
    mcc_id: UUID
    mcc_name: str
    collection_id: UUID
    quantity: Decimal
    can_count: int
    vlcc_id: UUID
    vlcc_name: str | None  # None when the asking MCC has Visible Member disabled
    is_deleted: bool
    quantity_collection_mode: QuantityCollectionMode


@dataclass(slots=True)
class MccSampleResult:
    sample_start: int
    sample_end: int
    is_mcc_exists: bool
    next_sample_number: int
    
    @property
    def range(self):
        return f"{self.sample_start}-{self.sample_end}"

    @property
    def out_of_range(self) -> bool:
        return self.sample_start < 0  or self.sample_end < self.next_sample_number
    
    @property
    def is_ok(self):
        return self.is_mcc_exists and (self.sample_start >= 0 and self.sample_end <= self.next_sample_number)

    @property
    def is_not_ok(self):
        return not self.is_ok


@dataclass(slots=True, frozen=True, kw_only=True)
class MccCollectionSummaryDto:
    total_quantity: float
    total_amount: float
    avg_fat: float
    avg_snf: float
    avg_rate: float
    active_users: int


@dataclass(slots=True, frozen=True, kw_only=True)
class MccDetailedCollectionDto:
    id: UUID
    collection_by: UUID | str | None = None
    collection_to: UUID | str | None = None
    collected_at: datetime
    member_code: str | None = None
    member_name: str | None = None
    role: Role | None = None
    shift: CollectionShift
    milk_type: MilkType = MilkType.COW
    quantity: Decimal
    quantity_collection_mode: QuantityCollectionMode = QuantityCollectionMode.MANUAL
    measurement_mode: MeasurementMode = MeasurementMode.MANUAL
    fat_percent: Decimal | None = None
    snf_percent: Decimal | None = None
    clr_value: Decimal | None = None
    rate_per_unit: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")
    payment_mode: PaymentMode = PaymentMode.CASH
    status: CollectionStatus = CollectionStatus.UNPAID
    sample_number: int | None = None
    can_count: int | None = None
    detection_value: Decimal | None = None
    mcc_type: MccType | None = None
    rank: int | None = None
    calibration_fat: Decimal | None = None
    calibration_snf: Decimal | None = None
    is_deleted: bool = False