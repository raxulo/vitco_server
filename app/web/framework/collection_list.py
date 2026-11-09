"""
Reading the collection list filters from the URL.

These values come from shared or hand-edited links, so anything invalid is ignored
instead of producing an error page.

Python 3.13+
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.domain.listing import CollectionPeriod
from app.modules.ratechart.domain.enums import MilkType

_MAX_LIMIT = 100
_SEARCH_LENGTH = 100
_PAGES_AROUND_CURRENT = 2


def clean_limit(limit: int) -> int:
    return min(max(limit, 1), _MAX_LIMIT)


def clean_search(value: str) -> str:
    return (value or "").strip()[:_SEARCH_LENGTH]


def parse_uuid(value: str) -> UUID | None:
    try:
        return UUID((value or "").strip())
    except ValueError:
        return None


def parse_milk_type(value: str) -> MilkType | None:
    try:
        return MilkType(int(value))
    except (ValueError, TypeError):
        return None


def parse_shift(value: str) -> CollectionShift | None:
    try:
        return CollectionShift(int(value))
    except (ValueError, TypeError):
        return None


def parse_day(value: str) -> date | None:
    """yyyy-mm-dd, as sent by a native date input."""
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_period(date_from: str, date_to: str, start_shift: str, end_shift: str) -> CollectionPeriod:
    return CollectionPeriod(
        start_day=parse_day(date_from),
        end_day=parse_day(date_to),
        start_shift=parse_shift(start_shift),
        end_shift=parse_shift(end_shift),
    ).in_order()


def period_model(period: CollectionPeriod) -> dict[str, Any]:
    """The period as the filter form shows it, after the ends are put in order."""
    return {
        "date_from": period.start_day.isoformat() if period.start_day else "",
        "date_to": period.end_day.isoformat() if period.end_day else "",
        "start_shift": "" if period.start_shift is None else int(period.start_shift),
        "end_shift": "" if period.end_shift is None else int(period.end_shift),
    }


def filter_query(**values: Any) -> str:
    """Current filters for the pager links; empty ones are left out so URLs stay short."""
    return urlencode({key: value for key, value in values.items() if value not in (None, "")})


def page_window(page: int, total_pages: int) -> list[int | None]:
    """Page numbers around the current one plus both ends; None marks a gap."""
    shown = {1, total_pages, *range(page - _PAGES_AROUND_CURRENT, page + _PAGES_AROUND_CURRENT + 1)}
    window: list[int | None] = []
    previous = 0
    for number in sorted(n for n in shown if 1 <= n <= total_pages):
        if number - previous > 1:
            window.append(None)
        window.append(number)
        previous = number
    return window
