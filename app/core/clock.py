"""
Enterprise Clock & DateTime System
==================================

Single Source of Truth for Date & Time across the entire application.
Configured for Indian Standard Time (IST / Asia/Kolkata, UTC+05:30).

Python 3.13+
"""

from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo


# -----------------------------------------------------------------------------
# Configuration: Indian Standard Time (IST)
# -----------------------------------------------------------------------------
TIMEZONE_NAME: str = "Asia/Kolkata"
TIMEZONE_LABEL: str = "IST"
IST: ZoneInfo = ZoneInfo(TIMEZONE_NAME)

# Set environment variable so any OS/process level library also defaults to IST
os.environ["TZ"] = TIMEZONE_NAME


# -----------------------------------------------------------------------------
# Core DateTime Functions
# -----------------------------------------------------------------------------

def now_ist() -> datetime:
    """
    Returns the current datetime in Indian Standard Time (timezone-aware).
    
    Example:
        current_time = now_ist()  # 2026-10-11 16:15:00+05:30
    """
    return datetime.now(IST)


def now_naive_ist() -> datetime:
    """
    Returns the current Indian datetime as a naive datetime (no tzinfo).
    
    Ideal for database storage (SQLite / Postgres naive DateTime columns)
    to prevent timezone offset mismatch during SQL string comparisons.
    """
    return datetime.now(IST).replace(tzinfo=None)


def today_ist() -> date:
    """
    Returns current date in Indian Standard Time.
    """
    return datetime.now(IST).date()


def to_ist(dt: datetime | str | None = None) -> datetime:
    """
    Safely converts any datetime (UTC, naive, or ISO string) to Indian Standard Time (IST).
    - If None: returns current Indian datetime.
    - If string: parses ISO string and converts to IST.
    - If naive datetime: assumes Indian time and attaches IST timezone.
    - If aware datetime: converts timezone to IST.
    """
    if dt is None:
        return now_ist()

    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)

    if not isinstance(dt, datetime):
        raise TypeError(f"Expected datetime or ISO string, got {type(dt)}")

    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)

    return dt.astimezone(IST)


def to_naive_ist(dt: datetime | str | None = None) -> datetime:
    """
    Converts any datetime (UTC or aware) to IST and strips tzinfo.
    This guarantees consistent date comparison in queries and DB storage.
    """
    aware = to_ist(dt)
    return aware.replace(tzinfo=None)


def day_bounds_ist(
    target: datetime | date | str | None = None,
) -> tuple[datetime, datetime]:
    """
    Returns (start_of_day, end_of_day) for a given date or datetime in IST.
    Defaults to today if target is None.
    
    Both returned datetimes are naive IST (00:00:00 and next day 00:00:00),
    matching database columns for `>= day_start AND < day_end` filters.
    
    Example:
        day_start, day_end = day_bounds_ist(query.collected_at)
        stmt.where(collected_at >= day_start, collected_at < day_end)
    """
    if target is None:
        d = today_ist()
    elif isinstance(target, datetime):
        d = to_ist(target).date()
    elif isinstance(target, date):
        d = target
    elif isinstance(target, str):
        try:
            d = datetime.fromisoformat(target).date()
        except ValueError:
            d = date.fromisoformat(target)
    else:
        d = today_ist()

    day_start = datetime.combine(d, time.min)
    day_end = day_start + timedelta(days=1)
    return day_start, day_end


def format_ist(
    dt: datetime | date | None = None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """
    Formats a datetime in IST. Defaults to current Indian time if dt is None.
    """
    if dt is None:
        return now_ist().strftime(fmt)
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return dt.strftime(fmt)
    return to_ist(dt).strftime(fmt)


# Alias for SQLAlchemy default callable on columns (e.g., default=get_ist_now)
get_ist_now = now_naive_ist
