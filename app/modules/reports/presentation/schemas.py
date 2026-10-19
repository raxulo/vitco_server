# presentation/schemas.py

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ReportRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date | None = None
    shift: int | None = None

    entries: int = 0
    quantity: Decimal = Decimal("0")
    amount: Decimal = Decimal("0")

    fat: Decimal = Decimal("0")
    snf: Decimal = Decimal("0")


class ReportResponse(BaseModel):

    report_type: str
    rows: list[ReportRow]

    page: int
    size: int
    total: int

    @property
    def pages(self) -> int:
        return (
            (self.total + self.size - 1)
            // self.size
            if self.size
            else 0
        )