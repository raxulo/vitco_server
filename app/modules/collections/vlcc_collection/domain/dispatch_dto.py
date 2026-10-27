from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
    MeasurementMode,
)


@dataclass(slots=True)
class DispatchDto:
    id: UUID
    vlcc_id: UUID
    collected_at: datetime
    shift: CollectionShift
    fat_percent: Decimal
    snf_percent: Decimal
    quantity: Decimal
    can_count: int
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode
    vlcc_name: str | None = None


@dataclass(slots=True)
class DispatchListDto:
    id: UUID
    vlcc_id: UUID
    vlcc_name: str
    collected_at: datetime
    shift: CollectionShift
    fat_percent: Decimal
    snf_percent: Decimal
    quantity: Decimal
    can_count: int
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode


@dataclass(slots=True)
class ShiftComparisonItemDto:
    date: date
    shift: CollectionShift
    vlcc_id: UUID
    vlcc_name: str
    collection_quantity: Decimal
    collection_fat: Decimal
    collection_snf: Decimal
    collection_count: int
    farmer_count: int
    dispatch_quantity: Decimal
    dispatch_fat: Decimal
    dispatch_snf: Decimal
    dispatch_can_count: int
    dispatch_count: int
    quantity_diff: Decimal
    fat_diff: Decimal | None
    snf_diff: Decimal | None
    status: str


@dataclass(slots=True)
class ComparisonSummaryDto:
    total_collected_qty: Decimal
    total_dispatched_qty: Decimal
    net_variance_qty: Decimal
    total_cans: int
    total_collections_count: int
    avg_collection_fat: Decimal
    avg_collection_snf: Decimal
    avg_dispatch_fat: Decimal
    avg_dispatch_snf: Decimal
    dispatch_ratio: float

