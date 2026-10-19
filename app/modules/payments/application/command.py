from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.modules.payments.domain.enums import (
    PaymentMethod,
    PaymentSourceType,
)


@dataclass(frozen=True, slots=True)
class PostPaymentCommand:

    sender_id: UUID
    receiver_id: UUID

    amount: Decimal

    source_type: PaymentSourceType
    payment_method: PaymentMethod

    idempotency_key: str

    source_id: UUID | None = None

    reference: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentPostingResult:

    transfer_id: UUID

    created: bool

    sender_balance: Decimal
    receiver_balance: Decimal

    sender_pair_balance: Decimal
    receiver_pair_balance: Decimal

    sender_ledger_id: UUID | None
    receiver_ledger_id: UUID | None