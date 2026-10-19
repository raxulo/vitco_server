"""
Common Settings Database Model

Reusable operational configuration for MCC, VLCC,
Dairy and other milk-collection entities.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Enum,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)

from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)


class SettingsModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "settings"

    # =========================================================
    # Analyzer
    # =========================================================

    analyzer_type: Mapped[AnalyzerType] = mapped_column(
        Enum(
            AnalyzerType,
            name="settings_analyzer_type_enum",
        ),
        nullable=False,
        default=AnalyzerType.TYPE_A,
    )

    analyzer_collection_mode: Mapped[CollectionMode] = mapped_column(
        Enum(
            CollectionMode,
            name="settings_analyzer_collection_mode_enum",
        ),
        nullable=False,
        default=CollectionMode.MANUAL,
    )

    # =========================================================
    # Weight
    # =========================================================

    weight_unit: Mapped[WeightUnit] = mapped_column(
        Enum(
            WeightUnit,
        ),
        nullable=False,
        default=WeightUnit.LITER,
    )

    weight_collection_mode: Mapped[CollectionMode] = mapped_column(
        Enum(
            CollectionMode,
        ),
        nullable=False,
        default=CollectionMode.MANUAL,
    )

    auto_tare_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # =========================================================
    # Collection Schedule
    # =========================================================

    morning_collection_start: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="06:00",
    )

    morning_collection_end: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="10:00",
    )

    evening_collection_start: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="12:00",
    )

    evening_collection_end: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="22:00",
    )

    # =========================================================
    # Printer / Receipt
    # =========================================================

    receipt_size: Mapped[ReceiptSize] = mapped_column(
        Enum(
            ReceiptSize,
        ),
        nullable=False,
        default=ReceiptSize.SMALL,
    )

    printer_type: Mapped[PrinterType] = mapped_column(
        Enum(
            PrinterType,
        ),
        nullable=False,
        default=PrinterType.NONE,
    )

    printer_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # =========================================================
    # Cattle
    # =========================================================

    cattle_type: Mapped[CattleType] = mapped_column(
        "supported_cattle_type",
        Enum(
            CattleType,
        ),
        nullable=False,
        default=CattleType.COW_AND_BUFFALO,
    )

    # =========================================================
    # Rate Chart
    # =========================================================

    max_rate_chart_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )

    # =========================================================
    # Permissions
    # =========================================================

    settings_edit_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    rate_chart_edit_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    master_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )