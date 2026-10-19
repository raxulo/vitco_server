from datetime import date
from pydantic import BaseModel, Field
from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)


class CreateRateChartRequest(BaseModel):

    chart_name: str = Field(..., min_length=1, max_length=150)
    chart_type: RateChartType
    milk_type: MilkType = Field(default=MilkType.MIXED)
    calculation_type: RateCalculationType = Field(default=RateCalculationType.FAT_AND_SNF)
    effective_from: date
    effective_to: date | None = None
    status: RateChartStatus = Field(default=RateChartStatus.ACTIVE)
    description: str | None = None


class UpdateRateChartRequest(BaseModel):

    chart_name: str = Field(..., min_length=1, max_length=150)
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None
    status: RateChartStatus
    description: str | None = None