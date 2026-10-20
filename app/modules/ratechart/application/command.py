from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)

from app.modules.administration.domain.enums import Role



from app.middleware.authentication import CurrentUser


@dataclass(slots=True)
class CreateRateChartCommand:

    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None = None
    status: RateChartStatus = RateChartStatus.ACTIVE
    description: str | None = None
    created_by: UUID | None = None
    # Logged-in user: an MCC / VLCC is limited to its max_rate_chart_count
    owner: CurrentUser | None = None


@dataclass(slots=True)
class UpdateRateChartCommand:

    id: UUID
    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None
    status: RateChartStatus
    description: str | None
    owner: CurrentUser | None = None


@dataclass(slots=True)
class DeleteRateChartCommand:

    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class SaveFormulaConfigCommand:

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
class GridRowInput:
    row_number: int
    fat: float
    snf: float
    rate: float


@dataclass(slots=True)
class SaveGridRowsCommand:

    rate_chart_id: UUID
    rows: list[GridRowInput]


@dataclass(slots=True)
class ProdataRowInput:
    row_number: int
    fat_min: float
    fat_max: float
    snf_min: float | None = None
    snf_max: float | None = None
    fat_rate_per_kg: float | None = None
    snf_rate_per_kg: float | None = None
    snf_cutoff: float | None = None
    snf_deduction: float | None = None


@dataclass(slots=True)
class SaveProdataRowsCommand:

    rate_chart_id: UUID
    rows: list[ProdataRowInput]


@dataclass(slots=True)
class GetRateChartQuery:

    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class ListRateChartsQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None
    owner: CurrentUser | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


@dataclass(slots=True)
class CreateRateChartAssignmentCommand:

    owner_type: Role
    owner_id: UUID
    rate_chart_id: UUID
    priority: int = 0
    is_default: bool = False
    created_by: UUID | None = None


@dataclass(slots=True)
class UpdateRateChartAssignmentCommand:

    id: UUID
    owner_type: Role
    owner_id: UUID
    rate_chart_id: UUID
    priority: int
    is_default: bool
    is_active: bool


@dataclass(slots=True)
class DeleteRateChartAssignmentCommand:

    id: UUID


@dataclass(slots=True)
class GetRateChartAssignmentQuery:

    id: UUID


@dataclass(slots=True)
class GetAssignmentsByOwnerQuery:

    owner_id: UUID


@dataclass(slots=True)
class ListRateChartAssignmentsQuery:

    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
