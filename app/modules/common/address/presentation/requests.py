from pydantic import BaseModel, Field


class CreateAddressRequest(BaseModel):

    line: str = Field(..., min_length=1, max_length=255)
    state: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=100)
    pincode: str = Field(..., min_length=5, max_length=10)


class UpdateAddressRequest(BaseModel):

    line: str | None = Field(None, min_length=1, max_length=255)
    state: str | None = Field(None, min_length=1, max_length=100)
    city: str | None = Field(None, min_length=1, max_length=100)
    pincode: str | None = Field(None, min_length=5, max_length=10)

    def is_valid_detail(self):
        if not any([self.line, self.state, self.city, self.pincode]):
            return False
        return True