"""
Support portal form helpers (Plan 25.3)

Small shared pieces for the management screens: a readable message for any validation or
business error, simple offset pagination and reading optional UUIDs from query strings.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode
from uuid import UUID

from fastapi.exceptions import ValidationException
from pydantic import ValidationError

from app.core.exceptions.base import ApplicationException

PAGE_SIZE = 20


def error_message(exc: Exception) -> str:
    """One sentence a person can act on, for every error a support form can raise."""
    if isinstance(exc, ApplicationException):
        return exc.message
    if isinstance(exc, ValidationError):
        for error in exc.errors():
            if "email" in [str(part) for part in error.get("loc", ())]:
                return "Enter a valid email address."
        first = exc.errors()[0] if exc.errors() else {}
        return str(first.get("msg") or "Please check the form.")
    if isinstance(exc, ValidationException):
        errors = exc.errors()
        text = errors if isinstance(errors, str) else (errors[0] if errors else "")
        text = str(text).strip()
        if text == "Password too short.":
            return "Password must be at least 8 characters."
        return text or "Please check the form."
    raise exc


FORM_ERRORS = (ApplicationException, ValidationError, ValidationException)


def optional_uuid(value: str | None) -> UUID | None:
    try:
        return UUID(str(value)) if value else None
    except (TypeError, ValueError):
        return None


def page_number(value: str | None) -> int:
    try:
        return max(1, int(value or 1))
    except (TypeError, ValueError):
        return 1


@dataclass(slots=True, kw_only=True)
class Page:
    total: int
    offset: int
    limit: int
    prev_url: str | None
    next_url: str | None


def build_page(path: str, params: dict[str, str | None], page: int, total: int, limit: int = PAGE_SIZE) -> Page:
    offset = (page - 1) * limit

    def url(number: int) -> str:
        query = {key: value for key, value in params.items() if value}
        if number > 1:
            query["page"] = str(number)
        return f"{path}?{urlencode(query)}" if query else path

    return Page(
        total=total,
        offset=offset,
        limit=limit,
        prev_url=url(page - 1) if page > 1 else None,
        next_url=url(page + 1) if offset + limit < total else None,
    )
