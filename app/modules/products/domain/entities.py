from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class Product:

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
    created_at: datetime
    updated_at: datetime | None


@dataclass(slots=True)
class ProductImage:

    id: UUID
    product_id: UUID
    media_id: UUID
    is_active: bool
