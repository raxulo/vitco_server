"""
Shared input validators for request models.

Used from Pydantic `field_validator`s so web forms and APIs reject the same
values with the same readable message.
"""

import re
from datetime import date, datetime

_DIGITS = re.compile(r"[0-9]+")
_MOBILE = re.compile(r"[0-9]{10}")


def digits_only(value: str, label: str) -> str:
    """Strip surrounding spaces; the rest must be ASCII digits only."""
    value = (value or "").strip()
    if not _DIGITS.fullmatch(value):
        raise ValueError(f"{label} must contain digits only")
    return value


def optional_digits(value: str | None, label: str) -> str | None:
    """Like `digits_only`, but an empty value is allowed and becomes None."""
    if value is None or not str(value).strip():
        return None
    return digits_only(str(value), label)


def indian_date(value: date | str | None, label: str) -> date | None:
    """A date written as dd/mm/yyyy (forms); ISO yyyy-mm-dd is still accepted for API clients."""
    if value is None or isinstance(value, date):
        return value
    value = value.strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"{label} must be a valid date in dd/mm/yyyy format")


def min_not_above_max(low: float | None, high: float | None, label: str) -> None:
    """A 0 / empty maximum means "not configured" and is not compared."""
    if low and high and low > high:
        raise ValueError(f"{label}: minimum ({low:g}) cannot be more than maximum ({high:g})")


_TIME = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def _minutes(value: str | None, label: str) -> int | None:
    """'HH:MM' -> minutes since midnight; empty means "not set"."""
    value = (value or "").strip()
    if not value:
        return None
    match = _TIME.fullmatch(value[:5])
    if not match:
        raise ValueError(f"{label} must be a valid time (HH:MM)")
    return int(match.group(1)) * 60 + int(match.group(2))


def shift_delay(value: str | None) -> str:
    """
    MCC shift delay as 'HH:MM' (hours 00-23, minutes 00-59). Empty means no delay ('00:00').
    A single-digit hour ('5:30') is padded to '05:30'.
    """
    value = (value or "").strip()
    if not value:
        return "00:00"
    if re.fullmatch(r"\d:\d\d", value):
        value = f"0{value}"
    if not _TIME.fullmatch(value):
        raise ValueError("Shift delay must be hours and minutes as HH:MM (00:00 to 23:59)")
    return value


def apply_shift_delay_rule(model) -> None:
    """The MCC shift delay can be at most the morning shift start time (user, 2026-11-14)."""
    delay = _minutes(model.shift_delay, "Shift delay")
    morning_start = _minutes(model.morning_collection_start, "Morning shift start time")
    if delay is not None and morning_start is not None and delay > morning_start:
        raise ValueError(
            f"Shift delay ({model.shift_delay}) cannot be more than the morning shift start time "
            f"({model.morning_collection_start[:5]})"
        )


def apply_shift_time_rules(model) -> None:
    """
    Collection shifts on a request model: each shift starts before it ends,
    and the morning shift ends before (or when) the evening shift starts.
    """
    morning_start = _minutes(model.morning_collection_start, "Morning shift start time")
    morning_end = _minutes(model.morning_collection_end, "Morning shift end time")
    evening_start = _minutes(model.evening_collection_start, "Evening shift start time")
    evening_end = _minutes(model.evening_collection_end, "Evening shift end time")

    if morning_start is not None and morning_end is not None and morning_start >= morning_end:
        raise ValueError(
            f"Morning shift: start time ({model.morning_collection_start}) must be before "
            f"end time ({model.morning_collection_end})"
        )
    if evening_start is not None and evening_end is not None and evening_start >= evening_end:
        raise ValueError(
            f"Evening shift: start time ({model.evening_collection_start}) must be before "
            f"end time ({model.evening_collection_end})"
        )
    if morning_end is not None and evening_start is not None and morning_end > evening_start:
        raise ValueError(
            f"Morning shift must end ({model.morning_collection_end}) before the evening shift "
            f"starts ({model.evening_collection_start})"
        )


def apply_milk_quality_rules(model) -> None:
    """
    Cow / buffalo FAT & SNF ranges on a request model (mutates it):
    every minimum <= its maximum, and buffalo minimum FAT is always
    cow maximum FAT + 0.1.
    """
    min_not_above_max(model.cow_min_fat, model.cow_max_fat, "Cow FAT")
    min_not_above_max(model.cow_min_snf, model.cow_max_snf, "Cow SNF")
    if model.cow_max_fat:
        model.buffalo_min_fat = round(model.cow_max_fat + 0.1, 2)
        if model.buffalo_max_fat and model.buffalo_min_fat > model.buffalo_max_fat:
            raise ValueError(
                f"Buffalo maximum FAT must be at least {model.buffalo_min_fat} "
                f"(cow maximum FAT + 0.1)"
            )
    min_not_above_max(model.buffalo_min_fat, model.buffalo_max_fat, "Buffalo FAT")
    min_not_above_max(model.buffalo_min_snf, model.buffalo_max_snf, "Buffalo SNF")


LIMIT_MAX = 99.99

_LIMIT_LABELS = {"fat": "FAT", "snf": "SNF", "min": "minimum", "max": "maximum"}


def limit_at_most(model, fields) -> None:
    """FAT / SNF limits have 2 digits, "." and 2 digits at most (up to 99.99)."""
    for name in fields:
        value = getattr(model, name, None)
        if value is not None and value > LIMIT_MAX:
            label = " ".join(_LIMIT_LABELS.get(part, part.title()) for part in name.split("_"))
            # min_fat / max_snf ... are the fixed-rate limits
            label = f"Fixed rate {label}" if name.startswith(("min_", "max_")) else label
            raise ValueError(f"{label} can be at most {LIMIT_MAX} (2 digits before and after the point)")


SAMPLE_CODE_MAX_DIGITS = 6


def sample_code(value, label: str) -> int | None:
    """A weight MCC sample code: digits only, at most 6 of them; empty -> None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not text.isdigit():
        raise ValueError(f"{label} must contain digits only")
    if len(text) > SAMPLE_CODE_MAX_DIGITS:
        raise ValueError(f"{label} can have at most {SAMPLE_CODE_MAX_DIGITS} digits")
    return int(text)


def apply_sample_rules(model, weight_type) -> None:
    """A weight MCC needs both sample codes, and the start code below the end code."""
    if model.mcc_type != weight_type:
        return
    if model.sample_start is None:
        raise ValueError("Sample start code is required for a Weight MCC")
    if model.sample_end is None:
        raise ValueError("Sample end code is required for a Weight MCC")
    if model.sample_start >= model.sample_end:
        raise ValueError(
            f"Sample start code ({model.sample_start}) must be less than sample end code ({model.sample_end})"
        )


def mobile_number(value: str | None, *, required: bool = True) -> str | None:
    """A 10-digit mobile number, digits only (a +91 / 91 / 0 prefix is dropped)."""
    value = (value or "").strip().replace(" ", "").replace("-", "")
    if value.startswith("+91") and len(value) == 13:
        value = value[3:]
    elif value.startswith("91") and len(value) == 12:
        value = value[2:]
    elif value.startswith("0") and len(value) == 11:
        value = value[1:]
    if not value:
        if required:
            raise ValueError("Mobile number is required")
        return None
    if not _MOBILE.fullmatch(value):
        raise ValueError("Mobile number must be exactly 10 digits")
    return value
