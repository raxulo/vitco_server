"""
Collection Clock (DECISION-029)

When a collection entered on the web is recorded, and in which shift.

- Entry time = now - the MCC's shift delay ("HH:MM"). A delay can move the entry
  to the previous day: 00:30 with a 05:20 delay is the previous day's 19:10.
- Shift of a moment: Morning before the unit's morning shift end, otherwise
  Evening (the dashboard's rule for the current shift). Without a morning end
  the day splits at 12:00.

Pure functions, no framework imports. Python 3.13+
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.modules.collections.mcc_collection.domain.enums import CollectionShift

NO_DELAY = "00:00"
_DEFAULT_MORNING_END = (12, 0)


def _hours_minutes(value: str | None) -> tuple[int, int] | None:
    """'HH:MM' (or 'HH:MM:SS') -> (hours, minutes); None when empty or unreadable."""
    parts = (value or "").strip().split(":")
    if len(parts) < 2:
        return None
    try:
        hours, minutes = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours, minutes


def shift_delay_of(value: str | None) -> timedelta:
    """A stored shift delay as a duration; empty or unreadable means none."""
    parsed = _hours_minutes(value)
    if parsed is None:
        return timedelta()
    return timedelta(hours=parsed[0], minutes=parsed[1])


def shift_at(moment: datetime, morning_end: str | None) -> CollectionShift:
    """Morning before the morning shift end, otherwise Evening."""
    hours, minutes = _hours_minutes(morning_end) or _DEFAULT_MORNING_END
    if (moment.hour, moment.minute) < (hours, minutes):
        return CollectionShift.MORNING
    return CollectionShift.EVENING


def collection_moment(
    now: datetime,
    shift_delay: str | None = None,
    morning_end: str | None = None,
) -> tuple[datetime, CollectionShift]:
    """Entry time (now - shift delay, to the second) and its shift."""
    moment = (now - shift_delay_of(shift_delay)).replace(microsecond=0)
    return moment, shift_at(moment, morning_end)
