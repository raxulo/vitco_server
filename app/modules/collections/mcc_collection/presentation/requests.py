from app.modules.mcc.domain.enums import MccType
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MilkType,
    QuantityCollectionMode,
    MeasurementMode,
    CollectionStatus,
)
from app.modules.masters.advanced.domain.enums import PaymentMode


class CreateMccCollectionRequest(BaseModel):

    mcc_id: UUID
    vlcc_id: UUID
    collection_date: datetime
    shift: CollectionShift
    milk_type: MilkType = MilkType.COW
    fat_percent: Decimal | None = None
    snf_percent: Decimal | None = None
    clr_value: Decimal | None = None
    quantity: Decimal = Field(..., gt=Decimal("0.00"))
    quantity_collection_mode: QuantityCollectionMode = Field(default=QuantityCollectionMode.MANUAL)
    measurement_mode: MeasurementMode = Field(default=MeasurementMode.MANUAL)
    rate_per_unit: Decimal = Field(default=Decimal("0.00"))
    total_amount: Decimal = Field(default=Decimal("0.00"))
    payment_mode: PaymentMode = Field(default=PaymentMode.CASH)
    status: CollectionStatus = Field(default=CollectionStatus.UNPAID)
    sample_number: int = 0
    can_count: int = 0
    mcc_type: MccType = Field(default=MccType.NORMAL)


class UpdateMccCollectionRequest(BaseModel):

    collection_number: str = Field(..., min_length=1, max_length=50)
    mcc_id: UUID
    vlcc_id: UUID
    collection_date: datetime
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None = None
    snf_percent: Decimal | None = None
    clr_value: Decimal | None = None
    quantity: Decimal = Field(..., gt=Decimal("0.000"))
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode
    rate_per_unit: Decimal
    total_amount: Decimal
    payment_mode: PaymentMode
    status: CollectionStatus
    sample_number: int
    can_count: int