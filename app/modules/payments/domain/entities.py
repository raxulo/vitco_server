
from app.modules.payments.domain.enums import LedgerEntryType
from app.modules.payments.domain.enums import PaymentStatus
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True, frozen=True)
class PaymentAccount:
    user_id: UUID
    balance: Decimal
    version: int
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class PaymentTransaction:
    id: UUID
    sequence_id: int

    from_user_id: UUID
    to_user_id: UUID

    amount: Decimal

    transaction_at: datetime

    idempotency_key: str

    status: PaymentStatus

    reversal_of_id: UUID | None

    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class PaymentLedgerEntry:
    id: int
    transaction_id: UUID
    user_id: UUID

    entry_type: LedgerEntryType

    amount: Decimal

    balance_before: Decimal
    balance_after: Decimal

    created_at: datetime


@dataclass(slots=True, frozen=True)
class PaymentPairBalance:
    low_user_id: UUID
    high_user_id: UUID

    low_user_balance: Decimal

    updated_at: datetime