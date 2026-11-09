"""
Public store API schemas.

Each response model lists exactly what is public, so a field added to a domain object
never becomes public by accident. Amounts serialise as strings to keep paise exact.

Python 3.13+
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Limit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0)]
Price = Annotated[Decimal, Field(ge=0, le=9_999_999_999, allow_inf_nan=False)]
Quantity = Annotated[int, Field(ge=1, le=50)]


class _Public(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# =========================================================
# REQUESTS
# =========================================================


class ProductListRequest(BaseModel):
    search: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=180)
    min_price: Price | None = None
    max_price: Price | None = None
    in_stock: bool = False
    sort: Literal["newest", "price_asc", "price_desc"] = "newest"
    limit: Limit = 24
    offset: Offset = 0


class AnimalListRequest(BaseModel):
    search: str | None = Field(default=None, max_length=100)
    type: str | None = Field(default=None, max_length=100)
    breed: UUID | None = None
    min_price: Price | None = None
    max_price: Price | None = None
    min_milk: Price | None = None
    lactation: Annotated[int, Field(ge=1, le=4)] | None = None
    location: str | None = Field(default=None, max_length=100)
    sort: Literal["newest", "price_asc", "price_desc", "milk_desc"] = "newest"
    limit: Limit = 24
    offset: Offset = 0


class EnquiryRequest(BaseModel):
    buyer_name: str = Field(max_length=120)
    buyer_phone: str = Field(max_length=20)
    location: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=1000)


class CartItem(BaseModel):
    variant_id: UUID
    quantity: Quantity


class CartQuoteRequest(BaseModel):
    items: list[CartItem] = Field(max_length=30)


class OrderRequest(BaseModel):
    items: list[CartItem] = Field(min_length=1, max_length=30)
    buyer_name: str = Field(max_length=120)
    buyer_phone: str = Field(max_length=20)
    address_line: str = Field(max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str = Field(max_length=10)
    notes: str | None = Field(default=None, max_length=500)
    checkout_token: UUID
    expected_total: Price


class TrackRequest(BaseModel):
    order_ref: str = Field(max_length=30)
    phone: str = Field(max_length=20)


# =========================================================
# RESPONSES
# =========================================================


class StoreOut(_Public):
    store_name: str
    tagline: str | None
    logo_url: str | None
    support_phone: str | None
    whatsapp_number: str | None
    support_email: str | None
    address: str | None
    delivery_charge: Decimal
    free_delivery_above: Decimal | None
    min_order_amount: Decimal
    cod_enabled: bool
    serviceable_pincodes: list[str]
    is_store_open: bool
    closed_message: str | None
    policies: dict[str, str]


class CategoryOut(_Public):
    name: str
    slug: str
    image_url: str | None


class AnimalTypeOut(_Public):
    name: str
    slug: str
    image_url: str | None


class BreedOut(_Public):
    id: UUID
    name: str


class BannerOut(_Public):
    title: str
    subtitle: str | None
    cta_label: str | None
    cta_url: str | None
    image_url: str
    mobile_image_url: str | None


class TrendingTagOut(_Public):
    label: str
    url: str


class ProductCardOut(_Public):
    slug: str
    title: str
    brand: str | None
    short_description: str | None
    price: Decimal
    mrp: Decimal
    discount_percent: int
    size: str
    other_sizes: int
    in_stock: bool
    image_url: str | None
    image_alt: str | None


class AnimalCardOut(_Public):
    slug: str
    title: str
    type_name: str
    breed_name: str | None
    status: str
    price: Decimal
    is_negotiable: bool
    milk_litres_per_day: Decimal | None
    lactation_number: int | None
    age_months: int | None
    location: str | None
    image_url: str | None
    image_alt: str | None


class HomeBlockOut(_Public):
    section_type: str
    title: str
    subtitle: str | None
    category_slug: str | None
    categories: list[CategoryOut]
    products: list[ProductCardOut]
    animals: list[AnimalCardOut]
    banners: list[BannerOut]


class HomeOut(BaseModel):
    store: StoreOut
    trending_tags: list[TrendingTagOut]
    hero_banners: list[BannerOut]
    blocks: list[HomeBlockOut]


class GalleryImageOut(_Public):
    url: str
    alt: str


class SizeOut(_Public):
    variant_id: UUID
    name: str
    price: Decimal
    mrp: Decimal
    discount_percent: int
    in_stock: bool
    is_default: bool
    few_left: int | None


class ProductDetailOut(_Public):
    slug: str
    title: str
    brand: str | None
    short_description: str | None
    description: str | None
    category_name: str
    category_slug: str
    specifications: list[dict[str, str]]
    sizes: list[SizeOut]
    images: list[GalleryImageOut]


class ProductPageOut(BaseModel):
    product: ProductDetailOut
    related: list[ProductCardOut]


class AnimalDetailOut(_Public):
    slug: str
    title: str
    type_name: str
    type_slug: str
    breed_name: str | None
    status: str
    gender: str
    price: Decimal
    is_negotiable: bool
    age_months: int | None
    lactation_number: int | None
    milk_litres_per_day: Decimal | None
    fat_percent: Decimal | None
    pregnancy_status: str
    pregnancy_months: int | None
    calf_details: str | None
    health_notes: str | None
    vaccination_notes: str | None
    village: str | None
    district: str | None
    state: str | None
    description: str | None
    images: list[GalleryImageOut]


class AnimalPageOut(BaseModel):
    animal: AnimalDetailOut
    similar: list[AnimalCardOut]


class CartLineOut(_Public):
    variant_id: UUID
    slug: str
    title: str
    size: str
    price: Decimal
    mrp: Decimal
    quantity: int
    line_total: Decimal
    image_url: str | None
    reduced_from: int | None
    is_out_of_stock: bool
    max_quantity: int


class CartOut(_Public):
    lines: list[CartLineOut]
    removed_count: int
    subtotal: Decimal
    delivery_charge: Decimal
    total: Decimal
    min_order_amount: Decimal
    below_minimum_by: Decimal
    free_delivery_gap: Decimal
    is_store_open: bool
    cod_enabled: bool
    can_check_out: bool


class TrackedLineOut(_Public):
    product_title: str
    variant_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class TrackedOrderOut(_Public):
    """Deliberately no buyer name or address: a reference and phone number may be shared."""

    order_ref: str
    status: str
    payment_method: str
    payment_status: str
    pincode: str
    subtotal: Decimal
    delivery_charge: Decimal
    total: Decimal
    cancel_reason: str | None
    created_at: object | None = None
    lines: list[TrackedLineOut]
