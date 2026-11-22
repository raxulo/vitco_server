# application/dto.py

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class LedgerResult:
    head: dict[str, Any] | None = None
    rows: list[dict[str, Any]] | None = None
    footer: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ReportMetadata:
    report_name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    time: str | None = None
    name: str | None = None
    owner_name: str | None = None
    code: str | None = None
    date: str | None = None
    uic_code: str | None = None
    address: str | None = None
    start_shift: str | None = None
    end_shift: str | None = None
    start_code: str | None = None   
    end_code: str | None = None 
    start_route: str | None = None
    end_route: str | None = None
    role: str | None = None

    @property
    def is_range(self):
        return self.start_date is not None and self.end_date is not None

    @property
    def is_code_range(self):
        return self.start_code is not None and self.end_code is not None

    @property
    def is_route_range(self):
        return self.start_route is not None and self.end_route is not None
    
    

@dataclass(frozen=True, slots=True)
class ReportResult:

    metadata: ReportMetadata
    report_type: str
    header: list[str]
    footer: dict[str, Any]

    total: int
    page: int
    size: int

    rows: list[dict[str, Any]] | None = None
    ledger: list[dict[str, Any]] | None = None
    # Column widths in percent; when set, every table of the report shares them
    column_widths: list[int] | None = None
    # Columns shown on the web only, left out of the API response: {row key: header label}
    web_only_columns: dict[str, str] | None = None
    

