from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.masters.advanced.domain.enums import (
    PaymentMode,
)


@dataclass(slots=True)
class CreateAdvanceCommand:

    advance_number: str
    advance_date: date
    user_id: UUID
    notes: str | None = None
    created_by: UUID | None = None


@dataclass(slots=True)
class UpdateAdvanceCommand:

    id: UUID
    advance_number: str
    advance_date: date
    user_id: UUID
    notes: str | None
    is_active: bool


@dataclass(slots=True)
class DeleteAdvanceCommand:

    id: UUID


@dataclass(slots=True)
class AdvanceItemInput:
    item_id: UUID
    item_name: str
    quantity: Decimal
    unit_rate: Decimal


@dataclass(slots=True)
class SaveAdvanceItemsCommand:

    advance_id: UUID
    items: list[AdvanceItemInput]


@dataclass(slots=True)
class RecordAdvancePaymentCommand:

    advance_id: UUID
    payment_date: date
    amount: Decimal
    payment_mode: PaymentMode
    reference_number: str | None = None
    notes: str | None = None
    created_by: UUID | None = None


@dataclass(slots=True)
class GetAdvanceQuery:

    id: UUID


@dataclass(slots=True)
class ListAdvancesQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
