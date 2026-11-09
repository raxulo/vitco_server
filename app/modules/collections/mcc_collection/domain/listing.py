"""
Filters and totals of the collection lists, shared by the VLCC and MCC collections.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.ratechart.domain.enums import MilkType


@dataclass(slots=True, frozen=True, kw_only=True)
class CollectionPeriod:
    """
    From one day and shift to another, such as 1 Nov evening to 5 Nov morning.

    A shift with its date is a boundary of the range. A shift without a date means
    entries of that shift only.
    """

    start_day: date | None = None
    end_day: date | None = None
    start_shift: CollectionShift | None = None
    end_shift: CollectionShift | None = None

    def in_order(self) -> CollectionPeriod:
        """Swaps the two ends when they were entered the wrong way round."""
        if self.start_day is None or self.end_day is None:
            return self
        start = (self.start_day, CollectionShift.MORNING if self.start_shift is None else self.start_shift)
        end = (self.end_day, CollectionShift.EVENING if self.end_shift is None else self.end_shift)
        if start <= end:
            return self
        return replace(
            self,
            start_day=self.end_day, end_day=self.start_day,
            start_shift=self.end_shift, end_shift=self.start_shift,
        )


@dataclass(slots=True, frozen=True, kw_only=True)
class VlccCollectionFilters:
    farmer_search: str | None = None  # farmer name or code
    vlcc_id: UUID | None = None
    milk_type: MilkType | None = None
    period: CollectionPeriod | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class MccCollectionFilters:
    vlcc_search: str | None = None  # VLCC name or code
    mcc_id: UUID | None = None
    vlcc_id: UUID | None = None
    milk_type: MilkType | None = None
    period: CollectionPeriod | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class CollectionTotals:
    """Covers every entry that matches the filters. Deleted entries are only counted apart."""

    total_quantity: Decimal = Decimal("0")
    total_amount: Decimal = Decimal("0")
    avg_fat: Decimal = Decimal("0")
    avg_snf: Decimal = Decimal("0")
    entries: int = 0
    deleted_entries: int = 0
