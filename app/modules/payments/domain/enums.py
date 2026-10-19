from enum import IntEnum

class PaymentSourceType(IntEnum):
    MANUAL = 1
    MILK_COLLECTION = 2
    ADJUSTMENT = 3
    ADVANCE = 4


class PaymentMethod(IntEnum):
    CASH = 1
    UPI = 2
    BANK_TRANSFER = 3
    ONLINE = 4
    SYSTEM = 5


class PaymentTransferStatus(IntEnum):
    PENDING = 1
    COMPLETED = 2
    FAILED = 3
    REVERSED = 4
    POSTED = 5


class LedgerEntryType(IntEnum):
    DEBIT = 1
    CREDIT = 2