"""
Settings Application DTOs
"""

from __future__ import annotations

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
class SettingsData:
    
    analyzer_type: AnalyzerType = AnalyzerType.TYPE_A

    analyzer_collection_mode: CollectionMode = (
        CollectionMode.MANUAL
    )

    weight_unit: WeightUnit = WeightUnit.LITER

    weight_collection_mode: CollectionMode = (
        CollectionMode.MANUAL
    )

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
class CreateSettingsCommand(SettingsData):
    created_by: UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class UpdateSettingsCommand(SettingsData):
    settings_id: UUID