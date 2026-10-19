from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

@dataclass(slots=True, frozen=True)
class BankAccountDto:
    id: UUID
    user_id: UUID
    account_holder: str
    bank_name: str | None
    account_number: str | None
    ifsc_code: str | None
    upi_id: str | None

@dataclass(slots=True, frozen=True)
class BankAccountInfoDto:
    account_holder: str
    bank_name: str | None
    account_number: str | None
    ifsc_code: str | None
    upi_id: str | None