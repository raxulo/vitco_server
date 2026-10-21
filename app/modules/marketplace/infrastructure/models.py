"""
Marketplace Database Infrastructure Models

Enterprise-grade SQLAlchemy models for:
- Hero Banners (MarketplaceBannerModel)
- Trending Tags (MarketplaceTrendingTagModel)
- Browse Categories (MarketplaceBrowseCategoryModel)
- Product Categories (ProductCategoryModel)
- Animal Types (AnimalTypeModel)
- Products (MarketplaceProductModel)
- Product Variants (ProductVariantModel)
- Product Offers (ProductOfferModel)
- Inventory Management (InventoryModel)
- Animal Listings (AnimalModel)
"""

from typing import Any

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base
from app.core.database.mixins import TimestampMixin, UUIDMixin
from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalListingStatus,
    AnimalType,
    MarketplaceOrderStatus,
    MarketplacePostType,
    PregnancyStatus,
    ProductOfferStatus,
    ProductStatus,
)


class MarketplaceBannerModel(Base, UUIDMixin, TimestampMixin):
    """Hero Banner Configuration for Marketplace Homepage."""

    __tablename__ = "marketplace_banners"

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(80), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cta_text: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cta_target_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bg_gradient: Mapped[str | None] = mapped_column(String(255), nullable=True)


    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketplaceTrendingTagModel(Base, UUIDMixin, TimestampMixin):
    """Trending Search Tags & Quick Links."""

    __tablename__ = "marketplace_trending_tags"

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    url_path: Mapped[str] = mapped_column(String(500), nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class MarketplaceBrowseCategoryModel(Base, UUIDMixin, TimestampMixin):
    """Browse Category Cards UI Metadata."""

    __tablename__ = "marketplace_browse_categories"

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    path_url: Mapped[str] = mapped_column(String(500), nullable=False)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ProductCategoryModel(Base, UUIDMixin):
    """Hierarchical Product Categories."""

    __tablename__ = "product_categories"

    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)

    __table_args__ = (
        Index("ix_product_categories_parent_active", "parent_id", "is_active"),
    )


class AnimalTypeModel(Base, UUIDMixin, TimestampMixin):
    """Master Animal Types (Cow, Buffalo, Goat, etc.)."""

    __tablename__ = "animal_types"

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true", index=True)


class MarketplaceProductModel(Base, UUIDMixin, TimestampMixin):
    """Master Catalog Product Items."""

    __tablename__ = "marketplace_products"

    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    images: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="product_status_enum", native_enum=False),
        nullable=False,
        default=ProductStatus.ACTIVE,
        index=True,
    )

    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )

    variants: Mapped[list[ProductVariantModel]] = relationship(
        "ProductVariantModel", back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_marketplace_products_category_status", "category_id", "status"),
        Index("ix_marketplace_products_featured_status", "is_featured", "status"),
    )


class ProductVariantModel(Base, UUIDMixin):
    """Product Variants (SKUs, Weights, Units)."""

    __tablename__ = "product_variants"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("marketplace_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    product: Mapped[MarketplaceProductModel] = relationship("MarketplaceProductModel", back_populates="variants")
    offers: Mapped[list[ProductOfferModel]] = relationship(
        "ProductOfferModel", back_populates="variant", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_product_variant_quantity_positive"),
        Index("ix_product_variants_product_active", "product_id", "is_active"),
    )


class ProductOfferModel(Base, UUIDMixin, TimestampMixin):
    """Seller Price Offers for Product Variants."""

    __tablename__ = "product_offers"

    variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    seller_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(80), nullable=True)
    badge_color: Mapped[str | None] = mapped_column(String(30), nullable=True)

    minimum_order_quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, default=Decimal("1"), server_default="1"
    )
    maximum_order_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)

    status: Mapped[ProductOfferStatus] = mapped_column(
        Enum(ProductOfferStatus, name="product_offer_status_enum", native_enum=False),
        nullable=False,
        default=ProductOfferStatus.DRAFT,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )

    variant: Mapped[ProductVariantModel] = relationship("ProductVariantModel", back_populates="offers")
    inventory: Mapped[InventoryModel | None] = relationship(
        "InventoryModel", back_populates="offer", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("variant_id", "seller_user_id", name="uq_product_offer_variant_seller"),
        CheckConstraint("price >= 0", name="ck_product_offer_price_non_negative"),
        CheckConstraint("compare_at_price IS NULL OR compare_at_price >= price", name="ck_product_offer_compare_price_valid"),
        CheckConstraint("discount_percent IS NULL OR (discount_percent >= 0 AND discount_percent <= 100)", name="ck_product_offer_discount_valid"),
        CheckConstraint("minimum_order_quantity > 0", name="ck_product_offer_min_quantity_positive"),
        CheckConstraint("maximum_order_quantity IS NULL OR maximum_order_quantity >= minimum_order_quantity", name="ck_product_offer_max_quantity_valid"),
        Index("ix_product_offers_seller_status", "seller_user_id", "status"),
        Index("ix_product_offers_variant_status", "variant_id", "status"),
    )


class InventoryModel(Base, UUIDMixin, TimestampMixin):
    """Real-time Inventory & Stock Tracking per Seller Offer."""

    __tablename__ = "product_inventory"

    offer_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_offers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    available_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0"), server_default="0"
    )
    reserved_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("0"), server_default="0"
    )
    low_stock_threshold: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), nullable=False, default=Decimal("5"), server_default="5"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    offer: Mapped[ProductOfferModel] = relationship("ProductOfferModel", back_populates="inventory")

    __table_args__ = (
        CheckConstraint("available_quantity >= 0", name="ck_inventory_available_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="ck_inventory_reserved_non_negative"),
        CheckConstraint("low_stock_threshold >= 0", name="ck_inventory_low_threshold_non_negative"),
        CheckConstraint("version > 0", name="ck_inventory_version_positive"),
    )


class AnimalModel(Base, UUIDMixin, TimestampMixin):
    """Cattle & Livestock Animal Listings."""

    __tablename__ = "animals"

    seller_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    animal_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("animal_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    breed: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    milk_yield_liters: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    lactation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pregnancy_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    badge: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    images: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_animals_price_non_negative"),
        CheckConstraint("discount_percent IS NULL OR (discount_percent >= 0 AND discount_percent <= 100)", name="ck_animals_discount_percent"),
        CheckConstraint("age_months IS NULL OR age_months >= 0", name="ck_animals_age_months_non_negative"),
        CheckConstraint("milk_yield_liters IS NULL OR milk_yield_liters >= 0", name="ck_animals_milk_yield_non_negative"),
        CheckConstraint("lactation IS NULL OR lactation >= 0", name="ck_animals_lactation_non_negative"),
    )


class MarketplaceOrderModel(Base, UUIDMixin, TimestampMixin):
    """Customer Orders placed on Marketplace."""

    __tablename__ = "marketplace_orders"

    # The logged-in buyer; NULL for guest orders placed from the public marketplace
    buyer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    order_ref: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    buyer_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False, default="cod")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.0"))
    items_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", index=True)


# Backwards compatibility aliases for existing module references
MarketplaceCategoryModel = ProductCategoryModel
AnimalListingModel = AnimalModel