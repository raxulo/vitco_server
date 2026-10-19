from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel


class ProductResponse(BaseModel):

    id: UUID
    name: str
    description: str | None
    price: Decimal
    discount_percent: Decimal
    profile_image_id: UUID | None
    address_id: UUID | None
    contact_name: str | None
    contact_number: str | None
    contact_email: str | None
    is_active: bool

    class Config:
        from_attributes = True