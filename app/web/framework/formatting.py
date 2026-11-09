"""
Display formatting for templates.

Python 3.13+
"""

from decimal import Decimal, InvalidOperation


def quantity(value) -> str:
    """A measure without trailing zeros: 14.50 -> 14.5, 14.00 -> 14."""
    try:
        return f"{Decimal(str(value)).normalize():f}"
    except (InvalidOperation, ValueError, TypeError):
        return "—"


def age_label(months) -> str:
    """Whole years read better for adult animals: 8 -> 8 months, 48 -> 4 yrs, 42 -> 3.5 yrs."""
    if months is None:
        return "—"
    if months < 12:
        return f"{months} month" + ("" if months == 1 else "s")
    years = quantity(Decimal(round(months / 6)) / 2)
    return f"{years} yr" + ("" if years == "1" else "s")


def inr(value) -> str:
    """Rupees with Indian digit grouping: 125000 -> ₹1,25,000; paise shown only when present."""
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return "—"

    sign = "-" if amount < 0 else ""
    whole, paise = f"{abs(amount):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])
    return f"{sign}₹{whole}" + ("" if paise == "00" else f".{paise}")
