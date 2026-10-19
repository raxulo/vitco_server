from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class ProductDto:

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


@dataclass(slots=True, frozen=True)
class ProductListDto:

    id: UUID
    name: str
    price: Decimal
    discount_percent: Decimal
    is_active: bool
