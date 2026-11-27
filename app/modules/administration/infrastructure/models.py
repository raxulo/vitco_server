from app.core.database.mixins import SoftDeleteMixin
from app.core.database.mixins import TimestampMixin
from app.core.database.mixins import UUIDMixin
from app.modules.administration.domain.enums import Role
import uuid

from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey, Enum,
    false,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.core.database.base import Base


class UserModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):

    __tablename__ = "users"

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    # 32, not 20: a soft delete stores "del_<6 hex>_" + the 10-digit number (migration 0002)
    mobile: Mapped[str | None] = mapped_column(
        String(32),
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[Role] = mapped_column(
        Enum(Role),
        nullable=False,
        default=Role.FARMER,
    )

    profile_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    # Self Brand (Admins only, set by Super Admin): everyone under the Admin sees
    # `brand_logo_url` on the web instead of the Vitco logo (migration 0005)
    self_brand: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default=false(),
        nullable=False,
    )

    brand_logo_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    last_login: Mapped[datetime | None]