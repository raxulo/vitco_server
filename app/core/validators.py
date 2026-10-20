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
        raise ValueError(f"{label}: minimum cannot be more than maximum")


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


def mobile_number(value: str | None, *, required: bool = True) -> str | None:
    """A 10-digit mobile number, digits only."""
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError("Mobile number is required")
        return None
    if not _MOBILE.fullmatch(value):
        raise ValueError("Mobile number must be exactly 10 digits")
    return value
