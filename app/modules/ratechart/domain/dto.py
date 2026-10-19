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


@dataclass(slots=True)
class RateChartAssignmentDto:

    id: UUID
    owner_type: Role
    owner_id: UUID
    rate_chart_id: UUID
    priority: int
    is_default: bool
    is_active: bool


@dataclass(slots=True, frozen=True)
class RateChartAssignmentListDto:

    id: UUID
    owner_type: Role
    owner_id: UUID
    rate_chart_id: UUID
    priority: int
    is_default: bool
    is_active: bool


@dataclass(slots=True)
class RateChartDto:

    id: UUID
    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None
    status: RateChartStatus
    description: str | None
    can_modify: bool = False
    owner_name: str | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class RateChartListDto:
    id: UUID
    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    effective_from: date
    status: RateChartStatus
    is_default: bool = False
    can_modify: bool = False
    owner_name: str | None = None
