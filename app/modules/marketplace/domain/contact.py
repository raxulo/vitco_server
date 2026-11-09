"""
Phone numbers typed by customers.

Python 3.13+
"""

import re

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


def normalize_indian_mobile(value: str) -> str | None:
    """Ten digits, or None when this is not an Indian mobile number. Accepts +91, 91 and 0 prefixes, spaces and dashes."""
    digits = re.sub(r"[\s\-()]", "", value or "")
    if digits.startswith("+91"):
        digits = digits[3:]
    elif len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if _INDIAN_MOBILE.match(digits) else None
