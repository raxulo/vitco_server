"""
Marketplace read models.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalStatus,
    HomeSectionType,
    PregnancyStatus,
)
from app.modules.marketplace.domain.merchandising import Banner, StoreSettings, TrendingTag


@dataclass(slots=True, kw_only=True)
class ProductFilters:
    search: str | None = None
    category_ids: set[UUID] | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    in_stock_only: bool = False
    sort: str = "newest"
    offset: int = 0
    limit: int = 24


@dataclass(slots=True, kw_only=True)
class AnimalFilters:
    search: str | None = None
    animal_type_id: UUID | None = None
    breed_id: UUID | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    min_milk: Decimal | None = None
    lactation: int | None = None
    location: str | None = None
    sort: str = "newest"
    offset: int = 0
    limit: int = 24


@dataclass(slots=True, kw_only=True)
class SizeOption:
    variant_id: UUID
    name: str
    price: Decimal
    mrp: Decimal
    in_stock: bool
    is_default: bool = False
    few_left: int | None = None  # set only at or below the low stock level

    @property
    def discount_percent(self) -> int:
        if self.mrp <= 0 or self.mrp <= self.price:
            return 0
        return int((self.mrp - self.price) * 100 / self.mrp)


@dataclass(slots=True, kw_only=True)
class GalleryImage:
    url: str
    alt: str


@dataclass(slots=True, kw_only=True)
class SitemapListing:
    slug: str
    updated_at: datetime | None = None


@dataclass(slots=True, kw_only=True)
class ProductDetail:
    slug: str
    title: str
    category_id: UUID
    category_name: str
    category_slug: str
    sizes: list[SizeOption]
    images: list[GalleryImage] = field(default_factory=list)
    brand: str | None = None
    short_description: str | None = None
    description: str | None = None
    specifications: list[dict[str, str]] = field(default_factory=list)

    @property
    def default_size(self) -> SizeOption:
        return next((size for size in self.sizes if size.is_default), self.sizes[0])


@dataclass(slots=True, kw_only=True)
class AnimalDetail:
    slug: str
    title: str
    price: Decimal
    type_name: str
    type_slug: str
    animal_type_id: UUID
    status: AnimalStatus
    gender: AnimalGender
    pregnancy_status: PregnancyStatus
    images: list[GalleryImage] = field(default_factory=list)
    breed_name: str | None = None
    is_negotiable: bool = False
    age_months: int | None = None
    lactation_number: int | None = None
    milk_litres_per_day: Decimal | None = None
    fat_percent: Decimal | None = None
    pregnancy_months: int | None = None
    calf_details: str | None = None
    health_notes: str | None = None
    vaccination_notes: str | None = None
    district: str | None = None
    state: str | None = None
    village: str | None = None
    description: str | None = None

    @property
    def location(self) -> str | None:
        return ", ".join(part for part in (self.village, self.district, self.state) if part) or None

    @property
    def is_sold(self) -> bool:
        return self.status == AnimalStatus.SOLD


@dataclass(slots=True, kw_only=True)
class BreedOption:
    id: UUID
    name: str


@dataclass(slots=True, kw_only=True)
class ProductCard:
    """Public view of a product; shows the default active size."""

    slug: str
    title: str
    price: Decimal
    mrp: Decimal
    size: str
    brand: str | None = None
    short_description: str | None = None
    image_url: str | None = None
    image_alt: str | None = None
    other_sizes: int = 0
    in_stock: bool = True

    @property
    def discount_percent(self) -> int:
        if self.mrp <= 0 or self.mrp <= self.price:
            return 0
        return int((self.mrp - self.price) * 100 / self.mrp)


@dataclass(slots=True, kw_only=True)
class AnimalCard:
    """Public view of an animal listing."""

    slug: str
    title: str
    price: Decimal
    type_name: str
    status: AnimalStatus
    is_negotiable: bool = False
    breed_name: str | None = None
    milk_litres_per_day: Decimal | None = None
    lactation_number: int | None = None
    age_months: int | None = None
    district: str | None = None
    state: str | None = None
    image_url: str | None = None
    image_alt: str | None = None

    @property
    def location(self) -> str | None:
        return ", ".join(part for part in (self.district, self.state) if part) or None


@dataclass(slots=True, kw_only=True)
class CategoryTile:
    name: str
    slug: str
    image_url: str | None = None


@dataclass(slots=True, kw_only=True)
class AnimalTypeTile:
    name: str
    slug: str
    image_url: str | None = None


@dataclass(slots=True, kw_only=True)
class HomeBlock:
    """One home section with something to show; kinds of content depend on its type."""

    section_type: HomeSectionType
    title: str
    subtitle: str | None = None
    category_slug: str | None = None
    categories: list[CategoryTile] = field(default_factory=list)
    products: list[ProductCard] = field(default_factory=list)
    animals: list[AnimalCard] = field(default_factory=list)
    banners: list[Banner] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class StoreFrame:
    """What every store page needs for its header and footer."""

    settings: StoreSettings
    trending_tags: list[TrendingTag] = field(default_factory=list)
    categories: list[CategoryTile] = field(default_factory=list)
    animal_types: list[AnimalTypeTile] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class HomePage:
    frame: StoreFrame
    hero_banners: list[Banner] = field(default_factory=list)
    blocks: list[HomeBlock] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class CatalogOverview:
    products_total: int = 0
    products_published: int = 0
    animals_total: int = 0
    animals_live: int = 0
    low_stock_variants: int = 0
    new_orders: int = 0
    new_enquiries: int = 0


@dataclass(slots=True, kw_only=True)
class LowStockItem:
    product_id: UUID
    product_title: str
    variant_name: str
    stock: int
    low_stock_threshold: int
