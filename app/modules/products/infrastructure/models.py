"""
Admin Entity
"""

from sqlalchemy import CheckConstraint
from decimal import Decimal
from sqlalchemy import Index
from sqlalchemy import ForeignKey
from uuid import UUID
from app.core.database.base import Base
from app.core.database.mixins import UUIDMixin, TimestampMixin

from sqlalchemy.orm import (Mapped, mapped_column)

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Index,
)


class ProductModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "products"

    # =========================================================
    # Basic
    # =========================================================

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # =========================================================
    # Pricing
    # =========================================================

    price: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
    )

    discount_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
    )

    # =========================================================
    # Media
    # =========================================================

    profile_image_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "media.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Contact / Address
    # =========================================================

    address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "addresses.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    contact_name: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )

    contact_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    contact_email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
    )

    # =========================================================
    # Status
    # =========================================================

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    # =========================================================
    # Constraints / Indexes
    # =========================================================

    __table_args__ = (
        CheckConstraint(
            "price >= 0",
            name="ck_product_price_non_negative",
        ),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_product_discount_percent",
        ),
        Index(
            "ix_products_active_name",
            "is_active",
            "name",
        ),
    )



class ProductImageModel(Base, UUIDMixin):

    __tablename__ = "product_images"

    product_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    media_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "media.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    __table_args__ = (
        Index(
            "ix_product_images_product_media",
            "product_id",
            "media_id",
        ),
        Index(
            "ix_product_images_product_active",
            "product_id",
            "is_active",
        ),
    )