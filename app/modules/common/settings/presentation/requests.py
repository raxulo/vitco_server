from pydantic import BaseModel, Field
from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)


class CreateSettingsRequest(BaseModel):

    analyzer_type: AnalyzerType = Field(default=AnalyzerType.TYPE_A)
    analyzer_collection_mode: CollectionMode = Field(default=CollectionMode.MANUAL)

    weight_unit: WeightUnit = Field(default=WeightUnit.LITER)
    weight_collection_mode: CollectionMode = Field(default=CollectionMode.MANUAL)
    auto_tare_enabled: bool = Field(default=False)

    morning_collection_start: str = Field(default="06:00")
    morning_collection_end: str = Field(default="10:00")
    evening_collection_start: str = Field(default="12:00")
    evening_collection_end: str = Field(default="22:00")

    receipt_size: ReceiptSize = Field(default=ReceiptSize.SMALL)
    printer_type: PrinterType = Field(default=PrinterType.NONE)
    printer_enabled: bool = Field(default=False)

    cattle_type: CattleType = Field(default=CattleType.COW_AND_BUFFALO)
    max_rate_chart_count: int = Field(default=5, ge=0)
    settings_edit_enabled: bool = Field(default=False)
    rate_chart_edit_enabled: bool = Field(default=False)
    master_enabled: bool = Field(default=False)


class UpdateSettingsRequest(BaseModel):

    analyzer_type: AnalyzerType | None = None
    analyzer_collection_mode: CollectionMode | None = None

    weight_unit: WeightUnit | None = None
    weight_collection_mode: CollectionMode | None = None
    auto_tare_enabled: bool | None = None

    morning_collection_start: str | None = None
    morning_collection_end: str | None = None
    evening_collection_start: str | None = None
    evening_collection_end: str | None = None

    receipt_size: ReceiptSize | None = None
    printer_type: PrinterType | None = None
    printer_enabled: bool | None = None

    cattle_type: CattleType | None = None
    max_rate_chart_count: int | None = None
    settings_edit_enabled: bool | None = None
    rate_chart_edit_enabled: bool | None = None
    master_enabled: bool | None = None