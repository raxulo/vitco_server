from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class BankAccount:

    id: UUID

    user_id: UUID

    account_holder: str

    bank_name: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None