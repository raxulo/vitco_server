"""
Numeric utility functions for formatting and truncating decimal numbers.

Python 3.13+
"""
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

# Float arithmetic leaves noise such as 10.1 * 3 == 30.299999999999997.
# Values are first normalised at this precision, then truncated.
_NOISE_PLACES = Decimal("1e-9")


def truncate_decimal(value: float | int | Decimal | str | None, digits: int = 2) -> Decimal:
    """
    Cut value to `digits` places after the decimal point — never rounds.

    Examples:
        truncate_decimal(234.78944)   -> Decimal("234.78")
        truncate_decimal(30.299999999999997) -> Decimal("30.30")
        truncate_decimal(4.1)         -> Decimal("4.10")
        truncate_decimal(1.23456, 3)  -> Decimal("1.234")
        truncate_decimal(None)        -> Decimal("0.00")
    """
    step = Decimal(1).scaleb(-digits)
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value if value not in (None, "") else 0))
        number = number.quantize(_NOISE_PLACES, rounding=ROUND_HALF_UP)
        return number.quantize(step, rounding=ROUND_DOWN)
    except (InvalidOperation, ValueError):
        return Decimal(0).quantize(step)


def truncate_float(value: float | int | Decimal | str | None, digits: int = 2) -> float:
    """Float form of `truncate_decimal` — e.g. 234.78944 -> 234.78."""
    return float(truncate_decimal(value, digits))


def fixed(value: float | int | Decimal | str | None, digits: int = 2) -> str:
    """
    Display string with exactly `digits` places, truncated — never rounded.

    Examples:
        fixed(234.78944) -> "234.78"
        fixed(4.1)       -> "4.10"
        fixed(None)      -> "0.00"
    """
    return format(truncate_decimal(value, digits), "f")


def to_fixed_2(value: float | int | Decimal | None) -> float:
    """
    Truncate value to exactly 2 digits after the decimal point without rounding.

    Examples:
        to_fixed_2(4.168) -> 4.16
        to_fixed_2(4.1)   -> 4.1
        to_fixed_2(0)     -> 0.0
    """
    if not value:
        return 0.0
    return truncate_float(value, 2)


def to_fixed_2_decimal(value: Decimal | float | int | str | None) -> Decimal:
    """
    Truncate Decimal to exactly 2 digits after the decimal point without rounding.

    Examples:
        to_fixed_2_decimal(Decimal("468.1389")) -> Decimal("468.13")
        to_fixed_2_decimal("45.6")              -> Decimal("45.60")
    """
    if not value:
        return Decimal("0.00")
    val_str = str(value)
    if "e" in val_str or "E" in val_str:
        val_str = f"{float(value):.8f}"
    if "." in val_str:
        int_part, dec_part = val_str.split(".", 1)
        dec_part = (dec_part + "00")[:2]
        return Decimal(f"{int_part}.{dec_part}")
    return Decimal(f"{val_str}.00")

