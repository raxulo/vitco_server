from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MilkType,
    QuantityCollectionMode,
    MeasurementMode,
    CollectionStatus,
)
from app.modules.masters.advanced.domain.enums import PaymentMode


class MccCollectionResponse(BaseModel):

    id: UUID
    collection_number: str
    mcc_id: UUID
    vlcc_id: UUID
    collection_date: datetime
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

    class Config:
        from_attributes = True