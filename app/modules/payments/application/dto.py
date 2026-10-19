from dataclasses import dataclass

@dataclass(slots=True, frozen=True)
class PaymentCollectionSummaryViaPeriodDto:
    total_collection_amount: float
    total_credit_amount: float
    total_debit_amount: float