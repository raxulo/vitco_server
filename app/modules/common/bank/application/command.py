from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

@dataclass(slots=True, kw_only=True)
class BankAccountData:
    account_holder: str
    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    @property
    def has_bank_detail(self) -> bool:
        return self.account_holder

@dataclass(slots=True)
class CreateBankAccountCommand:
    account_holder: str

    user_id: UUID | None = None


    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    @property
    def has_bank_detail(self) -> bool:
        return self.account_holder


@dataclass(slots=True)
class UpdateBankAccountCommand:

    id: UUID

    account_holder: str

    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None


@dataclass(slots=True, frozen=True)
class GetBankAccountQuery:

    id: UUID