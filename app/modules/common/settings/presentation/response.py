from uuid import UUID
from pydantic import BaseModel
from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)


class SettingsResponse(BaseModel):

    id: UUID
    analyzer_type: AnalyzerType
    analyzer_collection_mode: CollectionMode

    weight_collection_mode: CollectionMode
    auto_tare_enabled: bool

    morning_collection_start: str
    morning_collection_end: str
    evening_collection_start: str
    evening_collection_end: str

    receipt_size: ReceiptSize
    printer_type: PrinterType
    printer_enabled: bool

    cattle_type: CattleType
    max_rate_chart_count: int
    settings_edit_enabled: bool
    rate_chart_edit_enabled: bool
    master_enabled: bool = False
    weight_unit: WeightUnit = WeightUnit.KILOGRAM


    class Config:
        from_attributes = True