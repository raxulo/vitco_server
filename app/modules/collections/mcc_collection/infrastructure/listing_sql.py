"""
SQL for the collection list filters and totals, shared by the VLCC and MCC collections.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Float, and_, case, func, or_, type_coerce

from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.domain.listing import CollectionPeriod, CollectionTotals


def period_conditions(model: Any, period: CollectionPeriod | None) -> list:
    if period is None:
        return []
    period = period.in_order()
    conditions: list = []

    if period.start_day is not None:
        start = datetime.combine(period.start_day, time.min)
        conditions.append(model.collected_at >= start)
        if period.start_shift == CollectionShift.EVENING:
            # That day's morning is before the range; later days are inside it
            conditions.append(or_(model.collected_at >= start + timedelta(days=1), model.shift == CollectionShift.EVENING))

    if period.end_day is not None:
        last_day = datetime.combine(period.end_day, time.min)
        conditions.append(model.collected_at < last_day + timedelta(days=1))
        if period.end_shift == CollectionShift.MORNING:
            # That day's evening is after the range; earlier days are inside it
            conditions.append(or_(model.collected_at < last_day, model.shift == CollectionShift.MORNING))

    # Two different shifts without dates mean both of them, which is no filter at all
    dateless = {
        shift
        for shift, day in ((period.start_shift, period.start_day), (period.end_shift, period.end_day))
        if shift is not None and day is None
    }
    if len(dateless) == 1:
        conditions.append(model.shift == dateless.pop())
    return conditions


def _sum(expression: Any) -> Any:
    # Read as a plain number: as Numeric the result is rounded to the column's 2 places,
    # so a product of 279.415 becomes 279.41 and the average comes out too low
    return type_coerce(func.coalesce(func.sum(expression), 0), Float)


def totals_columns(model: Any) -> tuple:
    """Weighted averages use only entries with a FAT or SNF reading, so unread samples can't drag them down."""
    active = model.is_deleted.is_(False)
    read = and_(
        active,
        or_(func.coalesce(model.fat_percent, 0) != 0, func.coalesce(model.snf_percent, 0) != 0),
    )
    return (
        _sum(case((active, model.quantity), else_=0)).label("quantity"),
        _sum(case((active, model.total_amount), else_=0)).label("amount"),
        _sum(case((read, model.quantity), else_=0)).label("read_quantity"),
        _sum(case((read, model.quantity * model.fat_percent), else_=0)).label("fat_product"),
        _sum(case((read, model.quantity * model.snf_percent), else_=0)).label("snf_product"),
        func.coalesce(func.sum(case((active, 1), else_=0)), 0).label("entries"),
        func.count(model.id).label("all_entries"),
    )


def _exact(value: Any) -> Decimal:
    # SQLite adds in floats: 2490.56 can come back as 2490.5599999 and then truncate wrongly on screen
    return Decimal(str(round(float(value or 0), 6)))


def _average(product: Any, quantity: Decimal) -> Decimal:
    # Settled to 4 places first: a true 8.5 can arrive as 8.4999999, which the screen would truncate to 8.49
    return (_exact(product) / quantity).quantize(Decimal("0.0001"), ROUND_HALF_UP) if quantity else Decimal("0")


def totals_from_row(row: Any) -> CollectionTotals:
    read_quantity = _exact(row.read_quantity)
    entries = int(row.entries or 0)
    return CollectionTotals(
        total_quantity=_exact(row.quantity),
        total_amount=_exact(row.amount),
        avg_fat=_average(row.fat_product, read_quantity),
        avg_snf=_average(row.snf_product, read_quantity),
        entries=entries,
        deleted_entries=int(row.all_entries or 0) - entries,
    )
