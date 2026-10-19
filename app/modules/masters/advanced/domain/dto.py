from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.masters.advanced.domain.enums import AdvanceStatus


@dataclass(slots=True)
class AdvanceMasterDto:

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


@dataclass(slots=True, frozen=True)
class AdvanceMasterListDto:
    id: UUID
    advance_number: str
    advance_date: date
    user_id: UUID
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    status: AdvanceStatus
