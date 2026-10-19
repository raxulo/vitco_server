"""
Media Database Model

Stores metadata of uploaded media assets.
Actual binary content is handled by the storage layer.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)

from app.modules.media.domain.enums import (
    MediaCategory,
    MediaType,
)


class MediaModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "media"

    # =========================================================
    # Original File Information
    # =========================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # =========================================================
    # Classification
    # =========================================================

    media_type: Mapped[MediaType] = mapped_column(
        Enum(
            MediaType,
            name="media_type_enum",
        ),
        nullable=False,
        index=True,
    )

    category: Mapped[MediaCategory] = mapped_column(
        Enum(
            MediaCategory,
            name="media_category_enum",
        ),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    # =========================================================
    # Storage Information
    # =========================================================

    storage_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        index=True,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    extension: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # =========================================================
    # Owner
    # =========================================================

    uploaded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
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