from enum import IntEnum


class AdvanceStatus(IntEnum):
    UNPAID = 1
    PAID = 2
    OVERPAID = 3
    PARTIALLY_PAID = 4


class PaymentMode(IntEnum):
    CASH = 1
    ONLINE = 2
    BANK_TRANSFER = 3
    UPI = 4
    CHEQUE = 5