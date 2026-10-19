# app/modules/payments/domain/constants.py

from app.modules.payments.domain.enums import LedgerEntryType
from decimal import Decimal

ZERO = Decimal("0.00")


def apply_debit(
    balance: Decimal,
    amount: Decimal,
) -> Decimal:
    return balance - amount


def apply_credit(
    balance: Decimal,
    amount: Decimal,
) -> Decimal:
    return balance + amount


def calculate_balance_after(
    balance_before: Decimal,
    amount: Decimal,
    entry_type: LedgerEntryType,
) -> Decimal:

    if entry_type == LedgerEntryType.DEBIT:
        return balance_before - amount

    if entry_type == LedgerEntryType.CREDIT:
        return balance_before + amount

    raise ValueError(
        f"Unsupported ledger entry type: {entry_type}"
    )