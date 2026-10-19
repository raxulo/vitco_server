from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)
from app.modules.administration.domain.enums import Role


@dataclass(slots=True)
class RateChartAssignment:

    id: UUID
    owner_type: Role
    owner_id: UUID
    rate_chart_id: UUID
    priority: int
    is_default: bool
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None


@dataclass(slots=True)
class RateChart:

    id: UUID
    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None
    status: RateChartStatus
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None
    description: str | None = None
    can_modify: bool = False
    owner_name: str | None = None


@dataclass(slots=True)
class RateFormulaConfig:

    id: UUID
    rate_chart_id: UUID
    milk_type: MilkType
    cow_standard_fat: float | None = None
    cow_standard_snf: float | None = None
    cow_standard_rate: float | None = None
    buffalo_standard_fat: float | None = None
    buffalo_standard_snf: float | None = None
    buffalo_standard_rate: float | None = None
    cow_fat_percentage: float | None = None
    cow_snf_percentage: float | None = None
    buffalo_fat_percentage: float | None = None
    buffalo_snf_percentage: float | None = None


@dataclass(slots=True)
class RateGridRow:

    id: UUID
    rate_chart_id: UUID
    row_number: int
    fat: float
    snf: float
    rate: float


@dataclass(slots=True)
class ProdataRateRow:

    id: UUID
    rate_chart_id: UUID
    row_number: int
    fat_min: float
    fat_max: float
    snf_min: float | None = None
    snf_max: float | None = None
    fat_rate_per_kg: float | None = None
    snf_rate_per_kg: float | None = None
    snf_cutoff: float | None = None
    snf_deduction: float | None = None
