# application/queries.py

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.modules.reports.domain.enums import ReportType
from app.modules.collections.mcc_collection.domain.enums import MilkType
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.core.clock import now_naive_ist


@dataclass(frozen=True, slots=True)
class ReportQuery:
    actor_id: UUID
    report_type: ReportType
    start_date: date | None = None
    end_date: date | None = None
    milk_type: MilkType | None = None
    mcc_id: UUID | None = None
    vlcc_id: UUID | None = None
    route_code: str | None = None
    farmer_code: str | None = None
    code_from: str | None = None
    code_to: str | None = None
    route_from: str | None = None
    route_to: str | None = None
    start_shift: CollectionShift | None = None
    end_shift: CollectionShift | None = None
    page: int = 1
    size: int = 100

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size

    @property
    def formatted_start_date(self) -> str:
        if self.start_date:
            return f"{self.start_date.strftime('%d/%m/%Y')}"
        return ""

    @property
    def formatted_end_date(self) -> str:
        if self.end_date:
            return f"{self.end_date.strftime('%d/%m/%Y')}"
        return ""

    @property
    def formatted_start_shift(self) -> str:
        if self.start_shift is not None:
            return f"{'M' if self.start_shift == CollectionShift.MORNING else 'E'}"
        return ""

    @property
    def formatted_end_shift(self) -> str:
        if self.end_shift is not None:
            return f"{'M' if self.end_shift == CollectionShift.MORNING else 'E'}"
        return ""

    @property
    def formatted_time(self) -> str:
        return now_naive_ist().strftime('%H:%M:%S')