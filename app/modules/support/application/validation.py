"""
Support input rules shared by the handlers.

Python 3.13+
"""

from __future__ import annotations

import re

from app.core.validators import mobile_number
from app.modules.administration.domain.exceptions import InvalidMobileException
from app.modules.support.domain.exceptions import SupportValidationException
from app.modules.support.domain.permissions import (
    ASSIGNABLE_PERMISSIONS,
    SupportPermission,
)

_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,29}$")


def clean_name(value: str | None, *, label: str = "Name", minimum: int = 3, maximum: int = 120) -> str:
    text = (value or "").strip()
    if len(text) < minimum:
        raise SupportValidationException(f"{label} must be at least {minimum} characters.")
    if len(text) > maximum:
        raise SupportValidationException(f"{label} must be at most {maximum} characters.")
    return text


def clean_code(value: str | None) -> str:
    text = (value or "").strip().upper()
    if not _CODE.match(text):
        raise SupportValidationException(
            "Team code must be 2 to 30 letters, digits, dash or underscore, starting with a letter or digit."
        )
    return text


def clean_mobile(value: str | None) -> str:
    try:
        return mobile_number(value, required=True)
    except ValueError as exc:
        raise InvalidMobileException(f"{exc}.") from exc


def clean_permissions(values: list[str] | None) -> list[str]:
    """Known, assignable permissions only, without repeats and in a stable order."""
    chosen: set[SupportPermission] = set()
    for value in values or []:
        try:
            permission = SupportPermission(value)
        except ValueError as exc:
            raise SupportValidationException(f"Unknown permission: {value}.") from exc
        if permission not in ASSIGNABLE_PERMISSIONS:
            raise SupportValidationException(f"Permission {value} cannot be given to a team role.")
        chosen.add(permission)
    return sorted(str(permission) for permission in chosen)


def clean_text(value: str | None, *, label: str, minimum: int = 1, maximum: int = 4000) -> str:
    """Free text typed by a person: trimmed, with a length range."""
    text = (value or "").strip()
    if len(text) < minimum:
        raise SupportValidationException(f"{label} must be at least {minimum} characters.")
    if len(text) > maximum:
        raise SupportValidationException(f"{label} must be at most {maximum} characters.")
    return text


def clip(value: str | None, maximum: int) -> str | None:
    """Device details come from the app; keep them to the column size instead of failing the ticket."""
    text = (value or "").strip()
    return text[:maximum] or None
