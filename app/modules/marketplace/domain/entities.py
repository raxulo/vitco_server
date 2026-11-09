"""
Marketplace catalog entities.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalStatus,
    EnquiryStatus,
    PregnancyStatus,
    ProductStatus,
)


class ListingViewer(Protocol):
    """Whoever is reading or changing listings; the logged-in user satisfies this."""

    @property
    def id(self) -> UUID: ...

    @property
    def role_type(self) -> Role: ...


@dataclass(slots=True, kw_only=True)
class Enquiry:
    id: UUID
    animal_title: str
    buyer_name: str
    buyer_phone: str
    animal_id: UUID | None = None
    seller_user_id: UUID | None = None
    location: str | None = None
    message: str | None = None
    status: EnquiryStatus = EnquiryStatus.NEW
    admin_notes: str | None = None
    created_at: datetime | None = None


@dataclass(slots=True, kw_only=True)
class Category:
    id: UUID
    name: str
    slug: str
    parent_id: UUID | None = None
    description: str | None = None
    image_url: str | None = None
    sort_order: int = 0
    is_active: bool = True
    created_by: UUID | None = None


@dataclass(slots=True, kw_only=True)
class AnimalType:
    id: UUID
    name: str
    slug: str
    image_url: str | None = None
    sort_order: int = 0
    is_active: bool = True
    created_by: UUID | None = None


@dataclass(slots=True, kw_only=True)
class AnimalBreed:
    id: UUID
    animal_type_id: UUID
    name: str
    sort_order: int = 0
    is_active: bool = True
    created_by: UUID | None = None


@dataclass(slots=True, kw_only=True)
class ListingImage:
    id: UUID
    url: str
    media_id: UUID | None = None
    alt_text: str | None = None
    sort_order: int = 0


@dataclass(slots=True, kw_only=True)
class ProductVariant:
    id: UUID
    name: str
    mrp: Decimal
    price: Decimal
    stock: int = 0
    sku: str | None = None
    low_stock_threshold: int = 5
    is_default: bool = False
    is_active: bool = True
    sort_order: int = 0


@dataclass(slots=True, kw_only=True)
class Product:
    id: UUID
    seller_user_id: UUID
    category_id: UUID
    title: str
    slug: str
    brand: str | None = None
    short_description: str | None = None
    description: str | None = None
    specifications: list[dict[str, str]] = field(default_factory=list)
    status: ProductStatus = ProductStatus.DRAFT
    is_featured: bool = False
    is_trending: bool = False
    sort_order: int = 0
    variants: list[ProductVariant] = field(default_factory=list)
    images: list[ListingImage] = field(default_factory=list)
    created_by: UUID | None = None
    updated_by: UUID | None = None

    def problems(self) -> dict[str, str]:
        """What is wrong whatever the status; one message per field."""
        problems: dict[str, str] = {}
        if not self.title.strip():
            problems["title"] = "Enter a product name."
        skus = [variant.sku for variant in self.variants if variant.sku]
        if len(skus) != len(set(skus)):
            problems["variants"] = "Each size needs its own SKU."
        for variant in self.variants:
            if not variant.name.strip():
                problems["variants"] = "Every size needs a name, for example 1 L."
            elif variant.price < 0 or variant.stock < 0 or variant.low_stock_threshold < 0:
                problems["variants"] = f"{variant.name}: price and stock cannot be negative."
            elif variant.mrp < variant.price:
                problems["variants"] = f"{variant.name}: price cannot be above MRP."
        return problems

    def publish_problems(self) -> dict[str, str]:
        """What stops a shopper from seeing a complete listing."""
        problems: dict[str, str] = {}
        if not any(variant.is_active for variant in self.variants):
            problems["variants"] = "Add at least one active size before publishing."
        if not self.images:
            problems["images"] = "Add at least one image before publishing."
        return problems


@dataclass(slots=True, kw_only=True)
class Animal:
    id: UUID
    seller_user_id: UUID
    animal_type_id: UUID
    title: str
    slug: str
    price: Decimal
    breed_id: UUID | None = None
    gender: AnimalGender = AnimalGender.FEMALE
    is_negotiable: bool = False
    age_months: int | None = None
    lactation_number: int | None = None
    milk_litres_per_day: Decimal | None = None
    fat_percent: Decimal | None = None
    pregnancy_status: PregnancyStatus = PregnancyStatus.UNKNOWN
    pregnancy_months: int | None = None
    calf_details: str | None = None
    health_notes: str | None = None
    vaccination_notes: str | None = None
    state: str | None = None
    district: str | None = None
    village: str | None = None
    description: str | None = None
    status: AnimalStatus = AnimalStatus.DRAFT
    is_featured: bool = False
    is_trending: bool = False
    sort_order: int = 0
    images: list[ListingImage] = field(default_factory=list)
    created_by: UUID | None = None
    updated_by: UUID | None = None

    def problems(self) -> dict[str, str]:
        """What is wrong whatever the status; one message per field."""
        problems: dict[str, str] = {}
        if not self.title.strip():
            problems["title"] = "Enter a title."
        if self.price < 0:
            problems["price"] = "Price cannot be negative."
        for name, value, label in (
            ("age_months", self.age_months, "Age"),
            ("lactation_number", self.lactation_number, "Lactation"),
            ("milk_litres_per_day", self.milk_litres_per_day, "Milk per day"),
            ("pregnancy_months", self.pregnancy_months, "Pregnancy months"),
        ):
            if value is not None and value < 0:
                problems[name] = f"{label} cannot be negative."
        if self.fat_percent is not None and not 0 <= self.fat_percent <= 100:
            problems["fat_percent"] = "FAT must be between 0 and 100."
        return problems

    def publish_problems(self) -> dict[str, str]:
        """Buyers compare price, lactation and milk per day, so a live listing must show them."""
        problems: dict[str, str] = {}
        if self.price <= 0:
            problems["price"] = "Enter a price before publishing."
        if not self.images:
            problems["images"] = "Add at least one image before publishing."
        if self.gender == AnimalGender.FEMALE:
            if self.lactation_number is None:
                problems["lactation_number"] = "Enter the lactation number (0 if she has not calved)."
            if self.milk_litres_per_day is None:
                problems["milk_litres_per_day"] = "Enter milk litres per day (0 if she is not in milk)."
        return problems
