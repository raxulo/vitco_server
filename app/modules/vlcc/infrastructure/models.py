from uuid import UUID
from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import SoftDeleteMixin, TimestampMixin, UUIDMixin
from app.modules.common.settings.domain.enums import CollectionMode
from app.modules.vlcc.domain.enums import VlccType


class VlccModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):

    __tablename__ = "vlcc_master"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    uic_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    vlcc_code: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    contact_person: Mapped[str | None] = mapped_column(
        String(150)
    )

    address_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("addresses.id"),
        index=True,
        nullable=True
    )

    bank_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bank_accounts.id"),
        index=True,
        nullable=True
    )

    milk_quality_config_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("milk_quality_configs.id"),
        index=True,
        nullable=True,
    )

    settings_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("settings.id"),
        nullable=True
    )

    entry_mode: Mapped[CollectionMode] = mapped_column(
        Enum(CollectionMode),
        nullable=False,
        default=CollectionMode.MANUAL,
    )

    route_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    soc_percentage: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    farmer_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    assigned_chart_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    vlcc_type: Mapped[VlccType] = mapped_column(
        SmallInteger,
        nullable=False,
        default=VlccType.NORMAL,
        server_default="0",
    )
