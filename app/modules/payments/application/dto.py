from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True, frozen=True, kw_only=True)
class MilkPaymentDetailDto:
    """Milk behind a MILK_COLLECTION payment: the collection it paid for."""

    collection_id: UUID
    quantity: Decimal | None
    fat: Decimal | None
    snf: Decimal | None
    rate: Decimal | None


@dataclass(slots=True, frozen=True)
class PaymentCollectionSummaryViaPeriodDto:
    total_collection_amount: float
    total_credit_amount: float
    total_debit_amount: float