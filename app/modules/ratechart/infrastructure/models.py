"""
Rate Chart Database Models
"""
from app.modules.administration.domain.enums import Role
from sqlalchemy import Float

from datetime import date
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base
from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)

from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)


class RateChartModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "rate_charts"

    # =========================================================
    # Identity
    # =========================================================

    chart_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Chart Definition
    # =========================================================

    chart_type: Mapped[RateChartType] = mapped_column(
        Enum(
            RateChartType,
            name="rate_chart_type_enum",
        ),
        nullable=False,
        index=True,
    )

    milk_type: Mapped[MilkType | None] = mapped_column(
        Enum(
            MilkType,
        ),
        nullable=False,
        index=True,
        default=MilkType.MIXED,
    )

    calculation_type: Mapped[
        RateCalculationType
    ] = mapped_column(
        Enum(
            RateCalculationType,
            name="rate_calculation_type_enum",
        ),
        nullable=False,
        default=RateCalculationType.FAT_AND_SNF,
    )

    # =========================================================
    # Validity
    # =========================================================

    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    effective_to: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
    )

    status: Mapped[RateChartStatus] = mapped_column(
        Enum(
            RateChartStatus,
            name="rate_chart_status_enum",
        ),
        nullable=False,
        default=RateChartStatus.ACTIVE,
        index=True,
    )

    # =========================================================
    # Audit
    # =========================================================

    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # =========================================================
    # Description
    # =========================================================

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )


class RateFormulaConfigModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    __tablename__ = "rate_formula_configs"

    # =========================================================
    # Parent Formula
    # =========================================================

    rate_chart_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "rate_charts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Milk Type
    # =========================================================

    milk_type: Mapped[MilkType] = mapped_column(
        Enum(
            MilkType,
            name="formula_milk_type_enum",
        ),
        nullable=False,
    )

    # =========================================================
    # Standard Values
    # =========================================================

    cow_standard_fat: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    cow_standard_snf: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    cow_standard_rate: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    buffalo_standard_fat: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    buffalo_standard_snf: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    buffalo_standard_rate: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    # =========================================================
    # Calculation Percentages
    # =========================================================

    cow_fat_percentage: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    cow_snf_percentage: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    buffalo_fat_percentage: Mapped[float | None] = mapped_column(
        nullable=True,
    )

    buffalo_snf_percentage: Mapped[float | None] = mapped_column(
        nullable=True,
    )


class RateGridModel(
    Base,
    UUIDMixin,
):

    __tablename__ = "rate_grid_rows"

    rate_chart_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "rate_charts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    fat: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    snf: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )


class ProdataRateRowModel(
    Base,
    UUIDMixin,
):

    __tablename__ = "prodata_rate_rows"

    # =========================================================
    # Rate Chart
    # =========================================================

    rate_chart_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "rate_charts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # =========================================================
    # Row Order
    # =========================================================

    row_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    # =========================================================
    # FAT Range
    # =========================================================

    fat_min: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    fat_max: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    # =========================================================
    # SNF Range
    # =========================================================

    snf_min: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    snf_max: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # =========================================================
    # FAT / SNF Rate
    # =========================================================

    fat_rate_per_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    snf_rate_per_kg: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # =========================================================
    # SNF Cut-off
    # =========================================================

    snf_cutoff: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    # =========================================================
    # SNF Deduction
    # =========================================================

    snf_deduction: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )


class RateChartAssignmentModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "rate_chart_assignments"

    owner_type = mapped_column(
        Enum(
            Role,
            name="rate_chart_owner_type_enum",
        ),
        nullable=False,
        index=True,
    )
    # MCC / VLCC / SHOP

    owner_id = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    rate_chart_id = mapped_column(
        ForeignKey(
            "rate_charts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    priority = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    is_default = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    is_active = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_by = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
    )