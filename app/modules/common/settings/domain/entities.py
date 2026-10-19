"""
Settings Domain Entity
"""

from datetime import datetime

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


@dataclass(slots=True, kw_only=True)
class Settings:

    id: UUID

    # =========================================================
    # Analyzer
    # =========================================================

    analyzer_type: AnalyzerType = AnalyzerType.TYPE_A

    analyzer_collection_mode: CollectionMode = (
        CollectionMode.MANUAL
    )

    # =========================================================
    # Weight
    # =========================================================

    weight_unit: WeightUnit = WeightUnit.LITER

    weight_collection_mode: CollectionMode = (
        CollectionMode.MANUAL
    )

    auto_tare_enabled: bool = False

    # =========================================================
    # Collection Schedule
    # =========================================================

    morning_collection_start: str = "06:00"

    morning_collection_end: str = "10:00"

    evening_collection_start: str = "12:00"

    evening_collection_end: str = "22:00"

    # =========================================================
    # Printer / Receipt
    # =========================================================

    receipt_size: ReceiptSize = ReceiptSize.SMALL

    printer_type: PrinterType = PrinterType.NONE

    printer_enabled: bool = False

    # =========================================================
    # Cattle
    # =========================================================

    cattle_type: CattleType = (
        CattleType.COW_AND_BUFFALO
    )

    # =========================================================
    # Rate Chart
    # =========================================================

    max_rate_chart_count: int = 5

    # =========================================================
    # Permissions
    # =========================================================

    settings_edit_enabled: bool = False

    rate_chart_edit_enabled: bool = False

    master_enabled: bool = False

    created_by: UUID | None = None


    # =========================================================
    # Validation
    # =========================================================

    def validate(self) -> None:

        self._validate_schedule()
        self._validate_rate_chart_limit()
        self._validate_printer()

    def _validate_schedule(self) -> None:

        self._validate_time(
            self.morning_collection_start
        )

        self._validate_time(
            self.morning_collection_end
        )

        self._validate_time(
            self.evening_collection_start
        )

        self._validate_time(
            self.evening_collection_end
        )

    @staticmethod
    def _validate_time(value: str) -> None:

        parts = value.split(":")

        if len(parts) != 2:
            raise ValueError(
                "Invalid time format. Expected HH:MM."
            )

        hour, minute = parts

        if not (
            hour.isdigit()
            and minute.isdigit()
        ):
            raise ValueError(
                "Invalid time format. Expected HH:MM."
            )

        hour = int(hour)
        minute = int(minute)

        if not 0 <= hour <= 23:
            raise ValueError("Invalid hour.")

        if not 0 <= minute <= 59:
            raise ValueError("Invalid minute.")

    def _validate_rate_chart_limit(self) -> None:

        if self.max_rate_chart_count < 0:
            raise ValueError(
                "Maximum rate chart count cannot be negative."
            )

    def _validate_printer(self) -> None:

        if (
            self.printer_enabled
            and self.printer_type == PrinterType.NONE
        ):
            raise ValueError(
                "Printer type must be configured "
                "when printer is enabled."
            )

    def is_morning_collection_time(self, time: str) -> bool:
        """
        Check if the given time falls within the morning collection window.
        
        Args:
            time: Time in "HH:MM" format (24-hour)
            
        Returns:
            True if within morning window, False otherwise
        """
        self._validate_time(time)
        
        start_time = datetime.strptime(self.morning_collection_start, "%H:%M").time()
        end_time = datetime.strptime(self.morning_collection_end, "%H:%M").time()
        current_time = datetime.strptime(time, "%H:%M").time()
        
        return start_time <= current_time <= end_time

    def is_evening_collection_time(self, time: str) -> bool:
        """
        Check if the given time falls within the evening collection window.
        
        Args:
            time: Time in "HH:MM" format (24-hour)
            
        Returns:
            True if within evening window, False otherwise
        """
        self._validate_time(time)
        
        start_time = datetime.strptime(self.evening_collection_start, "%H:%M").time()
        end_time = datetime.strptime(self.evening_collection_end, "%H:%M").time()
        current_time = datetime.strptime(time, "%H:%M").time()
        
        return start_time <= current_time <= end_time

    def get_current_collection_period(self, time: str) -> str:
        """
        Get the current collection period (morning or evening) based on time.
        
        Args:
            time: Time in "HH:MM" format (24-hour)
            
        Returns:
            "morning" or "evening" or "break"
        """
        self._validate_time(time)
        
        if self.is_morning_collection_time(time):
            return "morning"
        elif self.is_evening_collection_time(time):
            return "evening"
        else:
            return "break"

    def is_collection_time(self, time: str) -> bool:
        """
        Check if the given time is within any collection window.
        """
        return (self.is_morning_collection_time(time) or 
                self.is_evening_collection_time(time))