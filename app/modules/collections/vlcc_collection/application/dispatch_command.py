from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


from app.middleware.authentication import CurrentUser
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
    MeasurementMode,
)


@dataclass(slots=True)
class CreateDispatchCommand:
    vlcc_id: UUID
    collected_at: datetime
    fat_percent: Decimal
    snf_percent: Decimal
    quantity: Decimal
    can_count: int
    shift: CollectionShift = CollectionShift.MORNING
    quantity_collection_mode: QuantityCollectionMode = QuantityCollectionMode.MANUAL
    measurement_mode: MeasurementMode = MeasurementMode.MANUAL
    owner: CurrentUser | None = None


@dataclass(slots=True)
class UpdateDispatchCommand:
    id: UUID
    vlcc_id: UUID
    collected_at: datetime
    fat_percent: Decimal
    snf_percent: Decimal
    quantity: Decimal
    can_count: int
    shift: CollectionShift = CollectionShift.MORNING
    quantity_collection_mode: QuantityCollectionMode = QuantityCollectionMode.MANUAL
    measurement_mode: MeasurementMode = MeasurementMode.MANUAL
    owner: CurrentUser | None = None


@dataclass(slots=True)
class DeleteDispatchCommand:
    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class GetDispatchQuery:
    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class ListDispatchesQuery:
    vlcc_id: UUID | None = None
    shift: CollectionShift | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    page: int = 1
    size: int = 20
    owner: CurrentUser | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
