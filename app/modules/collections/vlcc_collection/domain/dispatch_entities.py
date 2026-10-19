from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
    MeasurementMode,
)


@dataclass(slots=True)
class Dispatch:
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
    created_at: datetime
    updated_at: datetime | None
