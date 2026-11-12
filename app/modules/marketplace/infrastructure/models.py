"""
Marketplace database models.

All tables use the mkt_ prefix: the removed marketplace's tables stay in existing
databases under their old names (DECISION-015).

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
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
from app.core.database.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin
from app.core.database.types import NaiveDateTime
from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalStatus,
    BannerPlacement,
    EnquiryStatus,
    HomeSectionType,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PregnancyStatus,
    ProductStatus,
)


def _enum(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(enum_type, name=name, native_enum=False, length=30)


# =========================================================
# MASTERS
# =========================================================


class MarketplaceCategoryModel(Base, UUIDMixin, AuditMixin):
    """Nested product categories."""

    __tablename__ = "mkt_categories"

    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mkt_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class MarketplaceAnimalTypeModel(Base, UUIDMixin, AuditMixin):
    """Cow, buffalo, sheep, goat and others."""

    __tablename__ = "mkt_animal_types"

    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)


class MarketplaceAnimalBreedModel(Base, UUIDMixin, AuditMixin):
    """Breeds of one animal type."""

    __tablename__ = "mkt_animal_breeds"

    animal_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_animal_types.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("animal_type_id", "name", name="uq_mkt_animal_breed_type_name"),
    )


# =========================================================
# PRODUCTS
# =========================================================


class MarketplaceProductModel(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """A catalog item such as ghee or milk; sizes and prices live on its variants."""

    __tablename__ = "mkt_products"

    seller_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_categories.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    short_description: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [{"label": "Shelf life", "value": "6 months"}, ...]
    specifications: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ProductStatus] = mapped_column(
        _enum(ProductStatus, "mkt_product_status"), nullable=False, default=ProductStatus.DRAFT
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_trending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    variants: Mapped[list[MarketplaceProductVariantModel]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MarketplaceProductVariantModel.sort_order",
    )
    images: Mapped[list[MarketplaceProductImageModel]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MarketplaceProductImageModel.sort_order",
    )

    __table_args__ = (
        Index("ix_mkt_products_status_category", "status", "category_id"),
        Index("ix_mkt_products_status_featured", "status", "is_featured"),
        Index("ix_mkt_products_status_trending", "status", "is_trending"),
    )


class MarketplaceProductVariantModel(Base, UUIDMixin, AuditMixin):
    """One size of a product: its MRP, price and stock in whole packs."""

    __tablename__ = "mkt_product_variants"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    mrp: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    product: Mapped[MarketplaceProductModel] = relationship(back_populates="variants")

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_mkt_variant_price"),
        CheckConstraint("mrp >= price", name="ck_mkt_variant_mrp"),
        CheckConstraint("stock >= 0", name="ck_mkt_variant_stock"),
        CheckConstraint("low_stock_threshold >= 0", name="ck_mkt_variant_low_stock"),
    )


class MarketplaceProductImageModel(Base, UUIDMixin, AuditMixin):
    """Ordered gallery of a product; the lowest sort_order is the primary image."""

    __tablename__ = "mkt_product_images"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id: Mapped[UUID | None] = mapped_column(nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# =========================================================
# ANIMALS
# =========================================================


class MarketplaceAnimalModel(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """A cow, buffalo, sheep, goat or other animal for sale; bought through enquiry (DECISION-017)."""

    __tablename__ = "mkt_animals"

    seller_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    animal_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_animal_types.id", ondelete="RESTRICT"), nullable=False
    )
    breed_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mkt_animal_breeds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, unique=True, index=True)
    gender: Mapped[AnimalGender] = mapped_column(
        _enum(AnimalGender, "mkt_animal_gender"), nullable=False, default=AnimalGender.FEMALE
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_negotiable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lactation_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    milk_litres_per_day: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    fat_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    pregnancy_status: Mapped[PregnancyStatus] = mapped_column(
        _enum(PregnancyStatus, "mkt_pregnancy_status"), nullable=False, default=PregnancyStatus.UNKNOWN
    )
    pregnancy_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calf_details: Mapped[str | None] = mapped_column(String(300), nullable=True)
    health_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    vaccination_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    village: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AnimalStatus] = mapped_column(
        _enum(AnimalStatus, "mkt_animal_status"), nullable=False, default=AnimalStatus.DRAFT
    )
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_trending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    images: Mapped[list[MarketplaceAnimalImageModel]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="MarketplaceAnimalImageModel.sort_order",
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_mkt_animal_price"),
        CheckConstraint("age_months IS NULL OR age_months >= 0", name="ck_mkt_animal_age"),
        CheckConstraint("lactation_number IS NULL OR lactation_number >= 0", name="ck_mkt_animal_lactation"),
        CheckConstraint("milk_litres_per_day IS NULL OR milk_litres_per_day >= 0", name="ck_mkt_animal_milk"),
        CheckConstraint("fat_percent IS NULL OR (fat_percent >= 0 AND fat_percent <= 100)", name="ck_mkt_animal_fat"),
        CheckConstraint("pregnancy_months IS NULL OR pregnancy_months >= 0", name="ck_mkt_animal_pregnancy"),
        Index("ix_mkt_animals_status_type", "status", "animal_type_id"),
        Index("ix_mkt_animals_status_featured", "status", "is_featured"),
        Index("ix_mkt_animals_status_trending", "status", "is_trending"),
    )


class MarketplaceAnimalImageModel(Base, UUIDMixin, AuditMixin):
    """Ordered gallery of an animal; the lowest sort_order is the primary image."""

    __tablename__ = "mkt_animal_images"

    animal_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_animals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_id: Mapped[UUID | None] = mapped_column(nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# =========================================================
# STOREFRONT CONTENT
# =========================================================


class MarketplaceBannerModel(Base, UUIDMixin, AuditMixin):
    """Banner with an optional display window."""

    __tablename__ = "mkt_banners"

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cta_label: Mapped[str | None] = mapped_column(String(60), nullable=True)
    cta_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    mobile_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    placement: Mapped[BannerPlacement] = mapped_column(
        _enum(BannerPlacement, "mkt_banner_placement"), nullable=False, default=BannerPlacement.HOME_HERO
    )
    starts_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="ck_mkt_banner_window"),
        Index("ix_mkt_banners_placement_active", "placement", "is_active"),
    )


class MarketplaceHomeSectionModel(Base, UUIDMixin, AuditMixin):
    """Order and visibility of one home page section."""

    __tablename__ = "mkt_home_sections"

    section_type: Mapped[HomeSectionType] = mapped_column(
        _enum(HomeSectionType, "mkt_home_section_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mkt_categories.id", ondelete="SET NULL"), nullable=True
    )
    item_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("item_limit > 0", name="ck_mkt_home_section_limit"),
    )


class MarketplaceTrendingTagModel(Base, UUIDMixin, AuditMixin):
    """Trending search link shown on the store."""

    __tablename__ = "mkt_trending_tags"

    label: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MarketplaceSettingsModel(Base, UUIDMixin, AuditMixin):
    """Store settings; singleton_key keeps it to one row."""

    __tablename__ = "mkt_settings"

    singleton_key: Mapped[int] = mapped_column(Integer, nullable=False, default=1, unique=True)
    store_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(200), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    support_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    free_delivery_above: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_order_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    cod_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Empty means every pincode is served
    serviceable_pincodes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_store_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    closed_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # {"shipping": "...", "returns": "...", "terms": "...", "privacy": "..."}
    policies: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint("singleton_key = 1", name="ck_mkt_settings_singleton"),
        CheckConstraint("delivery_charge >= 0", name="ck_mkt_settings_delivery"),
        CheckConstraint("min_order_amount >= 0", name="ck_mkt_settings_min_order"),
    )


# =========================================================
# ORDERS & ENQUIRIES
# =========================================================


class MarketplaceOrderModel(Base, UUIDMixin, AuditMixin):
    """Order with its own buyer details, so guests need no account (DECISION-018)."""

    __tablename__ = "mkt_orders"

    order_ref: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    # One per checkout page: a repeated submit finds the order instead of creating another
    checkout_token: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    buyer_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    buyer_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    address_line: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pincode: Mapped[str] = mapped_column(String(10), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    delivery_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[PaymentMethod] = mapped_column(
        _enum(PaymentMethod, "mkt_payment_method"), nullable=False, default=PaymentMethod.COD
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        _enum(PaymentStatus, "mkt_payment_status"), nullable=False, default=PaymentStatus.PENDING
    )
    status: Mapped[OrderStatus] = mapped_column(
        _enum(OrderStatus, "mkt_order_status"), nullable=False, default=OrderStatus.PLACED, index=True
    )
    cancel_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    items: Mapped[list[MarketplaceOrderItemModel]] = relationship(
        back_populates="order", cascade="all, delete-orphan", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("subtotal >= 0", name="ck_mkt_order_subtotal"),
        CheckConstraint("delivery_charge >= 0", name="ck_mkt_order_delivery"),
        CheckConstraint("total >= 0", name="ck_mkt_order_total"),
    )


class MarketplaceOrderItemModel(Base, UUIDMixin, AuditMixin):
    """Order line; keeps title and price as they were when ordered."""

    __tablename__ = "mkt_order_items"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("mkt_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mkt_products.id", ondelete="SET NULL"), nullable=True, index=True
    )
    variant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mkt_product_variants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    seller_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_title: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_name: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mrp: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    order: Mapped[MarketplaceOrderModel] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_mkt_order_item_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_mkt_order_item_price"),
        CheckConstraint("line_total >= 0", name="ck_mkt_order_item_total"),
    )


class MarketplaceEnquiryModel(Base, UUIDMixin, AuditMixin):
    """Buyer enquiry about an animal; keeps the title in case the listing goes away."""

    __tablename__ = "mkt_enquiries"

    animal_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("mkt_animals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    seller_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    animal_title: Mapped[str] = mapped_column(String(200), nullable=False)
    buyer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    buyer_phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[EnquiryStatus] = mapped_column(
        _enum(EnquiryStatus, "mkt_enquiry_status"), nullable=False, default=EnquiryStatus.NEW, index=True
    )
    admin_notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
