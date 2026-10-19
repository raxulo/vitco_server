from dataclasses import dataclass
from uuid import UUID

from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateSettingsCommand:
    user_id: UUID | None = None

    analyzer_type: AnalyzerType = AnalyzerType.TYPE_A
    analyzer_collection_mode: CollectionMode = CollectionMode.MANUAL

    weight_unit: WeightUnit = WeightUnit.LITER
    weight_collection_mode: CollectionMode = CollectionMode.MANUAL
    auto_tare_enabled: bool = False

    morning_collection_start: str = "06:00"
    morning_collection_end: str = "10:00"
    evening_collection_start: str = "12:00"
    evening_collection_end: str = "22:00"

    receipt_size: ReceiptSize = ReceiptSize.SMALL
    printer_type: PrinterType = PrinterType.NONE
    printer_enabled: bool = False

    cattle_type: CattleType = CattleType.COW_AND_BUFFALO

    max_rate_chart_count: int = 5

    settings_edit_enabled: bool = False
    rate_chart_edit_enabled: bool = False
    master_enabled: bool = False


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateSettingsCommand:
    settings_id: UUID

    analyzer_type: AnalyzerType
    analyzer_collection_mode: CollectionMode

    weight_unit: WeightUnit
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