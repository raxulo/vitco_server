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
    ForeignKey, Enum
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

    mobile: Mapped[str | None] = mapped_column(
        String(20),
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

    last_login: Mapped[datetime | None]