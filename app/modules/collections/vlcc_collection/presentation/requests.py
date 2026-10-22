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


class CreateVlccCollectionRequest(BaseModel):

    vlcc_id: UUID
    farmer_id: UUID
    collection_date: datetime
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("99.99"))
    snf_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("99.99"))
    quantity: Decimal = Field(..., gt=Decimal("0.00"), lt=Decimal("1000000"))
    quantity_collection_mode: QuantityCollectionMode = Field(default=QuantityCollectionMode.MANUAL)
    measurement_mode: MeasurementMode = Field(default=MeasurementMode.MANUAL)
    rate_per_unit: Decimal = Field(default=Decimal("0.00"))
    total_amount: Decimal = Field(default=Decimal("0.00"))
    payment_mode: PaymentMode | None = Field(default=PaymentMode.CASH)
    status: CollectionStatus = Field(default=CollectionStatus.UNPAID)
    rank: int | None = None


class UpdateVlccCollectionRequest(BaseModel):

    collection_number: str = Field(..., min_length=1, max_length=50)
    vlcc_id: UUID
    farmer_id: UUID
    collection_date: datetime
    shift: CollectionShift
    milk_type: MilkType
    fat_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("99.99"))
    snf_percent: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("99.99"))
    quantity: Decimal = Field(..., gt=Decimal("0.00"), lt=Decimal("1000000"))
    quantity_collection_mode: QuantityCollectionMode
    measurement_mode: MeasurementMode
    rate_per_unit: Decimal
    total_amount: Decimal
    payment_mode: PaymentMode | None = Field(default=PaymentMode.CASH)
    status: CollectionStatus = Field(default=CollectionStatus.UNPAID)
    rank: int | None = None