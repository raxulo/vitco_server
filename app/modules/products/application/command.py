from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class CreateProductCommand:

    name: str
    price: Decimal
    description: str | None = None
    discount_percent: Decimal = Decimal("0.00")
    profile_image_id: UUID | None = None
    address_id: UUID | None = None
    contact_name: str | None = None
    contact_number: str | None = None
    contact_email: str | None = None


@dataclass(slots=True)
class UpdateProductCommand:

    id: UUID
    name: str
    price: Decimal
    description: str | None
    discount_percent: Decimal
    profile_image_id: UUID | None
    address_id: UUID | None
    contact_name: str | None
    contact_number: str | None
    contact_email: str | None
    is_active: bool


@dataclass(slots=True)
class DeleteProductCommand:

    id: UUID


@dataclass(slots=True)
class AddProductImageCommand:

    product_id: UUID
    media_id: UUID


@dataclass(slots=True)
class GetProductQuery:

    id: UUID


@dataclass(slots=True)
class ListProductsQuery:

    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
