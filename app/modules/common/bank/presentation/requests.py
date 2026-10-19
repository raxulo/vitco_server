from pydantic import BaseModel, Field


class CreateBankAccountRequest(BaseModel):

    account_holder: str = Field(..., min_length=1, max_length=150)
    bank_name: str | None = Field(None, max_length=150)
    account_number: str | None = Field(None, min_length=5, max_length=30)
    ifsc_code: str | None = Field(None, min_length=4, max_length=20)
    upi_id: str | None = Field(None, min_length=3, max_length=100)


class UpdateBankAccountRequest(BaseModel):

    account_holder: str | None = Field(None)
    bank_name: str | None = Field(None)
    account_number: str | None = Field(None)
    ifsc_code: str | None = Field(None)
    upi_id: str | None = Field(None)

    def is_valid_detail(self):
        if not any([self.account_holder, self.bank_name, self.account_number, self.ifsc_code, self.upi_id]):
            return False
        return True
        