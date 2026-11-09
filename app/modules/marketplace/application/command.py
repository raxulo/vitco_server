"""
Marketplace catalog commands.

Uploaded files are passed as received from the web layer (`new_images`, `new_image`).

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.modules.marketplace.domain.entities import ListingViewer
from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalStatus,
    BannerPlacement,
    EnquiryStatus,
    OrderStatus,
    PregnancyStatus,
    ProductStatus,
)


@dataclass(slots=True, kw_only=True)
class PlaceOrderCommand:
    items: dict[UUID, int]
    buyer_name: str
    buyer_phone: str
    address_line: str
    pincode: str
    checkout_token: str
    expected_total: Decimal
    city: str | None = None
    state: str | None = None
    notes: str | None = None
    buyer_user_id: UUID | None = None


@dataclass(slots=True, kw_only=True)
class MoveOrderCommand:
    owner: ListingViewer | None
    id: UUID
    status: OrderStatus
    cancel_reason: str | None = None


@dataclass(slots=True, kw_only=True)
class CreateEnquiryCommand:
    animal_slug: str
    buyer_name: str
    buyer_phone: str
    location: str | None = None
    message: str | None = None


@dataclass(slots=True, kw_only=True)
class UpdateEnquiryCommand:
    owner: ListingViewer | None
    id: UUID
    status: EnquiryStatus
    admin_notes: str | None = None


@dataclass(slots=True, kw_only=True)
class SaveBannerCommand:
    owner: ListingViewer | None
    title: str
    id: UUID | None = None
    subtitle: str | None = None
    cta_label: str | None = None
    cta_url: str | None = None
    placement: BannerPlacement = BannerPlacement.HOME_HERO
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sort_order: int = 0
    is_active: bool = True
    new_image: Any | None = None
    new_mobile_image: Any | None = None
    remove_mobile_image: bool = False


@dataclass(slots=True, kw_only=True)
class SaveHomeSectionCommand:
    owner: ListingViewer | None
    title: str
    id: UUID | None = None
    subtitle: str | None = None
    category_id: UUID | None = None
    item_limit: int = 8
    is_visible: bool = True


@dataclass(slots=True, kw_only=True)
class SaveTrendingTagCommand:
    owner: ListingViewer | None
    label: str
    url: str
    id: UUID | None = None
    sort_order: int = 0
    is_active: bool = True


@dataclass(slots=True, kw_only=True)
class SaveSettingsCommand:
    owner: ListingViewer | None
    store_name: str
    tagline: str | None = None
    support_phone: str | None = None
    whatsapp_number: str | None = None
    support_email: str | None = None
    address: str | None = None
    delivery_charge: Decimal = Decimal("0")
    free_delivery_above: Decimal | None = None
    min_order_amount: Decimal = Decimal("0")
    cod_enabled: bool = False
    serviceable_pincodes: list[str] = field(default_factory=list)
    is_store_open: bool = False
    closed_message: str | None = None
    policies: dict[str, str] = field(default_factory=dict)
    new_logo: Any | None = None
    remove_logo: bool = False


@dataclass(slots=True, kw_only=True)
class SaveCategoryCommand:
    owner: ListingViewer | None
    name: str
    id: UUID | None = None
    parent_id: UUID | None = None
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True
    new_image: Any | None = None
    remove_image: bool = False


@dataclass(slots=True, kw_only=True)
class SaveAnimalTypeCommand:
    owner: ListingViewer | None
    name: str
    id: UUID | None = None
    sort_order: int = 0
    is_active: bool = True
    new_image: Any | None = None
    remove_image: bool = False


@dataclass(slots=True, kw_only=True)
class SaveAnimalBreedCommand:
    owner: ListingViewer | None
    animal_type_id: UUID
    name: str
    id: UUID | None = None
    sort_order: int = 0
    is_active: bool = True


@dataclass(slots=True, kw_only=True)
class VariantInput:
    name: str
    mrp: Decimal
    price: Decimal
    id: UUID | None = None
    sku: str | None = None
    stock: int = 0
    low_stock_threshold: int = 5
    is_default: bool = False
    is_active: bool = True


@dataclass(slots=True, kw_only=True)
class SaveProductCommand:
    owner: ListingViewer | None
    category_id: UUID
    title: str
    id: UUID | None = None
    brand: str | None = None
    short_description: str | None = None
    description: str | None = None
    specifications: list[dict[str, str]] = field(default_factory=list)
    status: ProductStatus = ProductStatus.DRAFT
    is_featured: bool = False
    is_trending: bool = False
    sort_order: int = 0
    variants: list[VariantInput] = field(default_factory=list)
    keep_image_ids: list[UUID] = field(default_factory=list)
    new_images: list[Any] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class SaveAnimalCommand:
    owner: ListingViewer | None
    animal_type_id: UUID
    title: str
    price: Decimal
    id: UUID | None = None
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
    keep_image_ids: list[UUID] = field(default_factory=list)
    new_images: list[Any] = field(default_factory=list)
