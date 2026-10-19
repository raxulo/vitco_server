"""
Marketplace Application Commands & Queries

Dataclass commands for CQRS handlers:
- Hero Banners
- Trending Search Tags
- Browse Category Cards UI
- Hierarchical Product Categories
- Catalog Products & Offers
- Cattle & Livestock Listings
"""

from __future__ import annotations

from typing import Any
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from app.modules.marketplace.domain.enums import AnimalType, AnimalListingStatus, ProductStatus, ProductOfferStatus


# =========================================================
# Hero Banner Commands & Queries
# =========================================================
@dataclass(slots=True)
class CreateBannerCommand:
    title: str
    subtitle: str | None = None
    badge: str | None = None
    image_url: str | None = None
    image_file: Any | None = None
    cta_text: str | None = None
    cta_target_url: str | None = None
    bg_gradient: str | None = None
    sort_order: int = 0


@dataclass(slots=True)
class UpdateBannerCommand:
    id: UUID
    title: str
    subtitle: str | None = None
    badge: str | None = None
    image_url: str | None = None
    image_file: Any | None = None
    cta_text: str | None = None
    cta_target_url: str | None = None
    bg_gradient: str | None = None
    sort_order: int = 0
    is_active: bool = True



@dataclass(slots=True)
class DeleteBannerCommand:
    id: UUID | str


@dataclass(slots=True)
class GetBannerQuery:
    id: UUID


@dataclass(slots=True)
class ListBannersQuery:
    is_active_only: bool = True


# =========================================================
# Trending Search Tag Commands & Queries
# =========================================================
@dataclass(slots=True)
class CreateTrendingTagCommand:
    title: str
    url_path: str
    sort_order: int = 0


@dataclass(slots=True)
class UpdateTrendingTagCommand:
    id: UUID
    title: str
    url_path: str
    sort_order: int = 0
    is_active: bool = True


@dataclass(slots=True)
class DeleteTrendingTagCommand:
    id: UUID


@dataclass(slots=True)
class GetTrendingTagQuery:
    id: UUID


@dataclass(slots=True)
class ListTrendingTagsQuery:
    is_active_only: bool = True


# =========================================================
# Browse Category Card Commands & Queries
# =========================================================
@dataclass(slots=True)
class CreateBrowseCategoryCommand:
    title: str
    path_url: str
    subtitle: str | None = None
    color: str | None = None
    sort_order: int = 0


@dataclass(slots=True)
class UpdateBrowseCategoryCommand:
    id: UUID
    title: str
    path_url: str
    subtitle: str | None = None
    color: str | None = None
    sort_order: int = 0
    is_active: bool = True


@dataclass(slots=True)
class DeleteBrowseCategoryCommand:
    id: UUID


@dataclass(slots=True)
class GetBrowseCategoryQuery:
    id: UUID


@dataclass(slots=True)
class ListBrowseCategoriesQuery:
    is_active_only: bool = True


# =========================================================
# Product Category Commands & Queries
# =========================================================
@dataclass(slots=True)
class CreateProductCategoryCommand:
    name: str
    slug: str
    parent_id: UUID | None = None
    description: str | None = None
    icon_file: Any | None = None
    color: str | None = None
    sort_order: int = 0


@dataclass(slots=True)
class UpdateProductCategoryCommand:
    id: UUID | str
    name: str
    slug: str
    parent_id: UUID | None = None
    description: str | None = None
    icon: str | None = None
    icon_file: Any | None = None
    color: str | None = None
    sort_order: int = 0
    is_active: bool = True


@dataclass(slots=True)
class DeleteProductCategoryCommand:
    id: UUID | str


@dataclass(slots=True)
class GetProductCategoryQuery:
    id: UUID


@dataclass(slots=True)
class ListProductCategoriesQuery:
    is_active_only: bool = True


# Alias for backward compatibility
CreateCategoryCommand = CreateProductCategoryCommand


# =========================================================
# Catalog Product Commands & Queries
# =========================================================
@dataclass(slots=True)
class CreateProductCommand:
    category_id: UUID
    title: str
    slug: str
    description: str | None = None
    brand_name: str | None = None
    status: ProductStatus = ProductStatus.ACTIVE
    is_featured: bool = False


@dataclass(slots=True)
class UpdateProductCommand:
    id: UUID
    category_id: UUID
    title: str
    slug: str
    description: str | None = None
    brand_name: str | None = None
    status: ProductStatus = ProductStatus.ACTIVE
    is_featured: bool = False


@dataclass(slots=True)
class DeleteProductCommand:
    id: UUID


@dataclass(slots=True)
class GetProductQuery:
    id: UUID


@dataclass(slots=True)
class ListProductsQuery:
    category_id: UUID | None = None
    status: ProductStatus | None = None


# =========================================================
# Product Offer Commands
# =========================================================
@dataclass(slots=True)
class CreateProductOfferCommand:
    variant_id: UUID
    seller_user_id: UUID
    price: Decimal
    compare_at_price: Decimal | None = None
    discount_percent: Decimal | None = None
    badge: str | None = None
    badge_color: str | None = None
    minimum_order_quantity: Decimal = Decimal("1.000")
    maximum_order_quantity: Decimal | None = None
    status: ProductOfferStatus = ProductOfferStatus.ACTIVE


# =========================================================
# Cattle Animal Listing Commands & Queries
# =========================================================
@dataclass(slots=True)
class CreateAnimalListingCommand:
    seller_user_id: UUID
    animal_type_id: UUID
    title: str
    price: Decimal
    breed: str | None = None
    age_months: int | None = None
    milk_yield_liters: Decimal | None = None
    lactation: int | None = None
    pregnancy_date: date | None = None
    discount_percent: Decimal | None = None
    badge: str | None = None
    description: str | None = None


@dataclass(slots=True)
class UpdateAnimalListingCommand:
    id: UUID
    seller_user_id: UUID
    animal_type_id: UUID
    title: str
    price: Decimal
    breed: str | None = None
    age_months: int | None = None
    milk_yield_liters: Decimal | None = None
    lactation: int | None = None
    pregnancy_date: date | None = None
    discount_percent: Decimal | None = None
    badge: str | None = None
    description: str | None = None
    is_active: bool = True


@dataclass(slots=True)
class DeleteAnimalListingCommand:
    id: UUID


@dataclass(slots=True)
class GetAnimalListingQuery:
    id: UUID


# Aliases for backward compatibility
CreateAnimalCommand = CreateAnimalListingCommand
UpdateAnimalCommand = UpdateAnimalListingCommand
DeleteAnimalCommand = DeleteAnimalListingCommand

