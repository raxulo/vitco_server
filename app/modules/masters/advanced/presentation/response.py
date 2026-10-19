from datetime import date
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel
from app.modules.masters.advanced.domain.enums import AdvanceStatus


class AdvanceMasterResponse(BaseModel):

    id: UUID
    advance_number: str
    advance_date: date
    user_id: UUID
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    status: AdvanceStatus
    notes: str | None
    is_active: bool

    class Config:
        from_attributes = True