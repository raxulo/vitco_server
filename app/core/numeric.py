"""
Numeric utility functions for formatting and truncating decimal numbers.

Python 3.13+
"""
from decimal import Decimal


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
    val_str = str(value)
    if "e" in val_str or "E" in val_str:
        val_str = f"{float(value):.8f}"
    if "." in val_str:
        int_part, dec_part = val_str.split(".", 1)
        dec_part = (dec_part + "00")[:2]
        return float(f"{int_part}.{dec_part}")
    return float(value)


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

