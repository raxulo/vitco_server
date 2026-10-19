"""
Rate Chart API Schemas

Python 3.13+
"""
from app.modules.ratechart.domain.enums import RateChartStatus
from app.modules.ratechart.domain.enums import RateCalculationType
from app.modules.collections.mcc_collection.domain.enums import MilkType
from app.modules.ratechart.domain.enums import RateChartType

from datetime import date
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class FormulaConfigSchema(BaseModel):
    cow_standard_fat: float = 0.0
    cow_standard_snf: float = 0.0
    cow_standard_rate: float = 0.0
    buffalo_standard_fat: float = 0.0
    buffalo_standard_snf: float = 0.0
    buffalo_standard_rate: float = 0.0
    cow_fat_percentage: float = 0.0
    cow_snf_percentage: float = 0.0
    buffalo_fat_percentage: float = 0.0
    buffalo_snf_percentage: float = 0.0


class GridRowSchema(BaseModel):
    row_number: int | None = None
    fat: float = 0.0
    snf: float = 0.0
    rate: float = 0.0


class ProdataRowSchema(BaseModel):
    row_number: int | None = None
    fat_min: float = 0.0
    fat_max: float = 0.0
    snf_min: float | None = None
    snf_max: float | None = None
    kg_fat_rate: float | None = None
    kg_snf_rate: float | None = None
    snf_cut_off: float | None = None
    snf_deduction: float | None = None


class CreateRateChartApiRequest(BaseModel):
    chart_name: str
    chart_type: RateChartType
    milk_type: MilkType
    calculation_type: RateCalculationType
    effective_from: date
    effective_to: date | None
    status: RateChartStatus
    description: str | None
    formula_config: FormulaConfigSchema | None = None
    grids: list[GridRowSchema] | None = None
    prodata_rows: list[ProdataRowSchema] | None = None


class RateChartItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chart_name: str
    chart_type: Any
    milk_type: Any
    effective_from: date
    status: Any
    is_default: bool = False
    can_modify: bool = False
    owner_name: str | None = None


class RateChartListResponse(BaseModel):
    items: list[RateChartItemResponse]
    page: int
    size: int
    total: int
    total_pages: int


class RateChartDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chart_name: str
    chart_type: Any
    milk_type: Any
    calculation_type: Any
    effective_from: date
    effective_to: date | None = None
    status: Any
    description: str | None = None
    can_modify: bool = False
    owner_name: str | None = None
    formula_config: Any | None = None
    grids: list[Any] = []
    prodata_rows: list[Any] = []
