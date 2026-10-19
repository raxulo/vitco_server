from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, Field, EmailStr


class CreateProductRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    price: Decimal = Field(..., ge=Decimal("0.00"))
    discount_percent: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("100.00"))
    profile_image_id: UUID | None = None
    address_id: UUID | None = None
    contact_name: str | None = Field(None, max_length=150)
    contact_number: str | None = Field(None, max_length=20)
    contact_email: EmailStr | None = None


class UpdateProductRequest(BaseModel):

    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None
    price: Decimal = Field(..., ge=Decimal("0.00"))
    discount_percent: Decimal = Field(..., ge=Decimal("0.00"), le=Decimal("100.00"))
    profile_image_id: UUID | None = None
    address_id: UUID | None = None
    contact_name: str | None = Field(None, max_length=150)
    contact_number: str | None = Field(None, max_length=20)
    contact_email: EmailStr | None = None
    is_active: bool


class AddProductImageRequest(BaseModel):

    media_id: UUID