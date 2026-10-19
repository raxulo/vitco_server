from uuid import UUID
from pydantic import BaseModel


class AddressResponse(BaseModel):

    id: UUID
    user_id: UUID
    line: str
    state: str
    city: str
    pincode: str

    class Config:
        from_attributes = True