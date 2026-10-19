from uuid import UUID
from pydantic import BaseModel


class BankAccountResponse(BaseModel):

    id: UUID
    user_id: UUID
    account_holder: str
    bank_name: str | None
    account_number: str | None
    ifsc_code: str | None
    upi_id: str | None

    class Config:
        from_attributes = True