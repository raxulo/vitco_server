from datetime import date
from uuid import UUID
from pydantic import BaseModel
from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)


class RateChartResponse(BaseModel):

    id: UUID
    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None
    status: RateChartStatus
    description: str | None

    class Config:
        from_attributes = True