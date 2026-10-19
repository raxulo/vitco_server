from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.modules.masters.advanced.domain.enums import (
    AdvanceStatus,
    PaymentMode,
)


@dataclass(slots=True)
class AdvanceMaster:

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
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None


@dataclass(slots=True)
class AdvancePayItem:

    id: UUID
    advance_id: UUID
    item_id: UUID
    item_name: str
    quantity: Decimal
    unit_rate: Decimal
    total_amount: Decimal


@dataclass(slots=True)
class AdvancePayment:

    id: UUID
    advance_id: UUID
    payment_date: date
    amount: Decimal
    payment_mode: PaymentMode
    reference_number: str | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None
