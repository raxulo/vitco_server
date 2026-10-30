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
from app.modules.administration.domain.enums import Role
from app.modules.mcc.domain.enums import MccType



@dataclass(slots=True)
class VlccCollectionDto:

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
    clr_value : Decimal | None = None
    is_deleted: bool = False


@dataclass(slots=True, frozen=True, kw_only=True)
class VlccCollectionListDto:

    id: UUID
    vlcc_id: UUID
    farmer_id: UUID
    collected_at: datetime
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None
    snf_percent: Decimal | None
    quantity: Decimal
    rate_per_unit: Decimal
    total_amount: Decimal
    status: CollectionStatus
    vlcc_name: str | None = None
    farmer_name: str | None = None
    farmer_code: str | None = None
    is_deleted: bool = False


@dataclass(slots=True, frozen=True, kw_only=True)
class VlccCollectionSummaryDto:
    total_quantity: float
    total_amount: float
    avg_fat: float
    avg_snf: float
    avg_rate: float
    active_users: int


@dataclass(slots=True, frozen=True, kw_only=True)
class VlccDetailedCollectionDto:
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


