from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field
from app.modules.masters.advanced.domain.enums import PaymentMode


class CreateAdvanceRequest(BaseModel):

    advance_number: str = Field(..., min_length=1, max_length=50)
    advance_date: date
    user_id: UUID
    notes: str | None = None


class UpdateAdvanceRequest(BaseModel):

    advance_number: str = Field(..., min_length=1, max_length=50)
    advance_date: date
    user_id: UUID
    notes: str | None = None
    is_active: bool


class AdvanceItemRequest(BaseModel):
    item_id: UUID
    item_name: str = Field(..., min_length=1, max_length=150)
    quantity: Decimal = Field(..., gt=Decimal("0.000"))
    unit_rate: Decimal = Field(..., ge=Decimal("0.0000"))


class SaveAdvanceItemsRequest(BaseModel):
    items: list[AdvanceItemRequest]


class RecordAdvancePaymentRequest(BaseModel):
    payment_date: date
    amount: Decimal = Field(..., gt=Decimal("0.00"))
    payment_mode: PaymentMode
    reference_number: str | None = None
    notes: str | None = None