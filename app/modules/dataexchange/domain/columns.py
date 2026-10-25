"""
Data Exchange Column Specs

One declarative definition per sheet drives the template, the export rows,
the import parsing and the Instructions sheet. Pure Python — no Excel
library and no framework, so the same rules serve every entity.

Python 3.13+
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time
from enum import IntEnum
from typing import Any

from app.core.validators import mobile_number


class ColumnKind(IntEnum):

    TEXT = 0
    CODE = 1
    INT = 2
    FLOAT = 3
    BOOL = 4
    ENUM = 5
    EMAIL = 6
    MOBILE = 7
    TIME = 8
    PINCODE = 9
    ACCOUNT_NUMBER = 10
    IFSC = 11
    PASSWORD = 12

    @property
    def label(self) -> str:
        return {
            ColumnKind.TEXT: "Text",
            ColumnKind.CODE: "Code (text)",
            ColumnKind.INT: "Whole number",
            ColumnKind.FLOAT: "Number",
            ColumnKind.BOOL: "YES / NO",
            ColumnKind.ENUM: "One of the listed values",
            ColumnKind.EMAIL: "Email",
            ColumnKind.MOBILE: "10-digit mobile",
            ColumnKind.TIME: "Time HH:MM",
            ColumnKind.PINCODE: "6-digit pincode",
            ColumnKind.ACCOUNT_NUMBER: "Account number (digits)",
            ColumnKind.IFSC: "IFSC code",
            ColumnKind.PASSWORD: "Password",
        }[self]


class Section(IntEnum):

    ENTITY = 0
    USER = 1
    ADDRESS = 2
    BANK = 3
    SETTINGS = 4
    MILK_QUALITY = 5
    RATE = 6

    @property
    def fill(self) -> str:
        """Header fill colour (hex RGB, no '#')."""
        return {
            Section.ENTITY: "DCFCE7",
            Section.USER: "DBEAFE",
            Section.ADDRESS: "FFEDD5",
            Section.BANK: "EDE9FE",
            Section.SETTINGS: "FEF9C3",
            Section.MILK_QUALITY: "FEE2E2",
            Section.RATE: "E0F2FE",
        }[self]

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


# Excel shows these as text ("@") so long numbers and leading zeros survive
_TEXT_FORMAT_KINDS = frozenset({
    ColumnKind.CODE,
    ColumnKind.MOBILE,
    ColumnKind.PINCODE,
    ColumnKind.ACCOUNT_NUMBER,
    ColumnKind.IFSC,
    ColumnKind.TIME,
})

_BOOL_TRUE = frozenset({"YES", "Y", "TRUE", "1"})
_BOOL_FALSE = frozenset({"NO", "N", "FALSE", "0"})

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_PINCODE = re.compile(r"[1-9][0-9]{5}")
_ACCOUNT = re.compile(r"[0-9]{6,20}")
_IFSC = re.compile(r"[A-Z]{4}0[A-Z0-9]{6}")
_TIME = re.compile(r"([01]?[0-9]|2[0-3]):([0-5][0-9])(:[0-5][0-9])?")
_HEADER_SEPARATORS = re.compile(r"[\s_\-]+")


# =========================================================
# SPECS
# =========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class ColumnSpec:

    key: str
    header: str
    section: Section
    kind: ColumnKind
    required: bool = False
    choices: tuple[tuple[str, int], ...] = ()       # (label, value) for ENUM
    min_value: float | None = None
    max_value: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    help: str = ""
    example: str = ""
    export_only: bool = False
    import_only: bool = False                        # e.g. password: never exported

    @property
    def is_text_format(self) -> bool:
        return self.kind in _TEXT_FORMAT_KINDS

    @property
    def display_header(self) -> str:
        return f"{self.header} *" if self.required else self.header

    @property
    def dropdown(self) -> tuple[str, ...]:
        """Values for an Excel list validation (empty when the column has none)."""
        if self.kind is ColumnKind.BOOL:
            return ("YES", "NO")
        if self.kind is ColumnKind.ENUM:
            return tuple(label for label, _ in self.choices)
        return ()


@dataclass(slots=True, frozen=True, kw_only=True)
class SheetSpec:

    name: str
    columns: tuple[ColumnSpec, ...]
    key_column: str                                  # the upsert key, e.g. "farmer_code"

    def export_columns(self) -> tuple[ColumnSpec, ...]:
        return tuple(column for column in self.columns if not column.import_only)

    def import_columns(self) -> tuple[ColumnSpec, ...]:
        return tuple(column for column in self.columns if not column.export_only)

    def column(self, key: str) -> ColumnSpec:
        for column in self.columns:
            if column.key == key:
                return column
        raise KeyError(key)


def normalise_header(text: Any) -> str:
    """'Farmer Code *', 'farmer code' and 'FARMER_CODE' all become 'farmer_code'."""
    value = str(text or "").strip().rstrip("*").strip().lower()
    return _HEADER_SEPARATORS.sub("_", value).strip("_")


@dataclass(slots=True, frozen=True, kw_only=True)
class HeaderMap:
    """Where each spec column sits in a sheet's header row."""

    indexes: dict[str, int] = field(default_factory=dict)       # column key -> 0-based index
    missing_required: tuple[str, ...] = ()                     # display headers
    unknown: tuple[str, ...] = ()
    duplicates: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.missing_required

    @classmethod
    def build(cls, sheet: SheetSpec, raw_headers: tuple[Any, ...] | list[Any]) -> HeaderMap:
        by_name = {normalise_header(column.header): column for column in sheet.import_columns()}
        by_name.update({normalise_header(column.key): column for column in sheet.import_columns()})

        indexes: dict[str, int] = {}
        unknown: list[str] = []
        duplicates: list[str] = []
        for index, raw in enumerate(raw_headers):
            name = normalise_header(raw)
            if not name:
                continue
            column = by_name.get(name)
            if column is None:
                unknown.append(str(raw).strip())
            elif column.key in indexes:
                duplicates.append(str(raw).strip())
            else:
                indexes[column.key] = index

        missing = tuple(
            column.display_header
            for column in sheet.import_columns()
            if column.required and column.key not in indexes
        )
        return cls(
            indexes=indexes,
            missing_required=missing,
            unknown=tuple(unknown),
            duplicates=tuple(duplicates),
        )


# =========================================================
# PARSE (Excel -> Python)
# =========================================================

@dataclass(slots=True, frozen=True)
class ParsedCell:

    value: Any = None
    error: str | None = None
    blank: bool = False


_BLANK = ParsedCell(blank=True)


def parse_cell(spec: ColumnSpec, raw: Any) -> ParsedCell:
    """
    Convert one raw cell to its Python value, or explain why it is invalid.

    A blank cell is never an error here: "required" is decided by the importer,
    because on update a blank cell means "keep the stored value".
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return _BLANK
    try:
        return ParsedCell(value=_PARSERS[spec.kind](spec, raw))
    except ValueError as error:
        return ParsedCell(error=f"{spec.header}: {error}")


def _text(spec: ColumnSpec, raw: Any) -> str:
    if isinstance(raw, float) and raw.is_integer():
        value = str(int(raw))
    else:
        value = str(raw).strip()
    if spec.min_length is not None and len(value) < spec.min_length:
        raise ValueError(f"must be at least {spec.min_length} characters")
    if spec.max_length is not None and len(value) > spec.max_length:
        raise ValueError(f"must be at most {spec.max_length} characters")
    return value


def _code(spec: ColumnSpec, raw: Any) -> str:
    # A number cell holding a code must be whole (101 or 101.0 -> "101", 101.5 is a typo)
    return _text(spec, _as_digits_if_integral(raw) if isinstance(raw, float) else raw)


def _int(spec: ColumnSpec, raw: Any) -> int:
    number = _number(raw)
    if not float(number).is_integer():
        raise ValueError("must be a whole number")
    value = int(number)
    _check_range(spec, value)
    return value


def _float(spec: ColumnSpec, raw: Any) -> float:
    value = float(_number(raw))
    _check_range(spec, value)
    return value


def _bool(spec: ColumnSpec, raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    text = _as_digits_if_integral(raw) if isinstance(raw, (int, float)) else str(raw).strip().upper()
    if text in _BOOL_TRUE:
        return True
    if text in _BOOL_FALSE:
        return False
    raise ValueError("must be YES or NO")


def _enum(spec: ColumnSpec, raw: Any) -> int:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        number = _as_digits_if_integral(raw)
        for _, value in spec.choices:
            if str(value) == number:
                return value
    else:
        wanted = normalise_header(raw)
        for label, value in spec.choices:
            if normalise_header(label) == wanted or str(value) == wanted:
                return value
    allowed = ", ".join(label for label, _ in spec.choices)
    raise ValueError(f"must be one of: {allowed}")


def _email(spec: ColumnSpec, raw: Any) -> str:
    value = str(raw).strip().lower()
    if not _EMAIL.fullmatch(value) or len(value) > 255:
        raise ValueError("is not a valid email address")
    return value


def _mobile(spec: ColumnSpec, raw: Any) -> str:
    try:
        text = _as_digits_if_integral(raw) if isinstance(raw, (int, float)) else str(raw)
        return mobile_number(text, required=True)
    except ValueError:
        raise ValueError("must be exactly 10 digits") from None


def _time(spec: ColumnSpec, raw: Any) -> str:
    if isinstance(raw, datetime):
        raw = raw.time()
    if isinstance(raw, time):
        return f"{raw.hour:02d}:{raw.minute:02d}"
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and 0 <= raw < 1:
        # A time-formatted Excel cell holds a fraction of a day (0.25 = 06:00)
        minutes = round(raw * 24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
    match = _TIME.fullmatch(str(raw).strip())
    if not match:
        raise ValueError("must be a time like 06:30")
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _pincode(spec: ColumnSpec, raw: Any) -> str:
    value = _as_digits_if_integral(raw) if isinstance(raw, (int, float)) else str(raw).strip()
    if not _PINCODE.fullmatch(value):
        raise ValueError("must be a 6-digit pincode")
    return value


def _account_number(spec: ColumnSpec, raw: Any) -> str:
    value = _as_digits_if_integral(raw) if isinstance(raw, (int, float)) else str(raw).strip().replace(" ", "")
    if not _ACCOUNT.fullmatch(value):
        raise ValueError("must be 6 to 20 digits")
    return value


def _ifsc(spec: ColumnSpec, raw: Any) -> str:
    value = str(raw).strip().upper()
    if not _IFSC.fullmatch(value):
        raise ValueError("must be a valid 11-character IFSC code (e.g. SBIN0001234)")
    return value


def _password(spec: ColumnSpec, raw: Any) -> str:
    value = str(raw)
    if spec.min_length is not None and len(value) < spec.min_length:
        raise ValueError(f"must be at least {spec.min_length} characters")
    if len(value) > (spec.max_length or 128):
        raise ValueError("is too long")
    return value


_PARSERS = {
    ColumnKind.TEXT: _text,
    ColumnKind.CODE: _code,
    ColumnKind.INT: _int,
    ColumnKind.FLOAT: _float,
    ColumnKind.BOOL: _bool,
    ColumnKind.ENUM: _enum,
    ColumnKind.EMAIL: _email,
    ColumnKind.MOBILE: _mobile,
    ColumnKind.TIME: _time,
    ColumnKind.PINCODE: _pincode,
    ColumnKind.ACCOUNT_NUMBER: _account_number,
    ColumnKind.IFSC: _ifsc,
    ColumnKind.PASSWORD: _password,
}


def _as_digits_if_integral(raw: int | float) -> str:
    """Excel returns 9876543210 or 9876543210.0 for a number cell; codes need '9876543210'."""
    if isinstance(raw, float):
        if not raw.is_integer():
            raise ValueError("must not contain decimals")
        return str(int(raw))
    return str(raw)


def _number(raw: Any) -> float | int:
    if isinstance(raw, bool):
        raise ValueError("must be a number")
    if isinstance(raw, (int, float)):
        return raw
    try:
        return float(str(raw).strip().replace(",", ""))
    except ValueError:
        raise ValueError("must be a number") from None


def _check_range(spec: ColumnSpec, value: float) -> None:
    if spec.min_value is not None and value < spec.min_value:
        raise ValueError(f"must be at least {_plain(spec.min_value)}")
    if spec.max_value is not None and value > spec.max_value:
        raise ValueError(f"must be at most {_plain(spec.max_value)}")


def _plain(number: float) -> str:
    return str(int(number)) if float(number).is_integer() else str(number)


# =========================================================
# FORMAT (Python -> Excel)
# =========================================================

def format_cell(spec: ColumnSpec, value: Any) -> Any:
    """Inverse of parse_cell, used for export rows."""
    if value is None:
        return None
    if spec.kind is ColumnKind.BOOL:
        return "YES" if value else "NO"
    if spec.kind is ColumnKind.ENUM:
        if isinstance(value, str):
            for label, choice in spec.choices:
                if label.upper() == value.upper():
                    return label
        try:
            number = int(value)
            for label, choice in spec.choices:
                if choice == number:
                    return label
            return str(number)
        except (ValueError, TypeError):
            return str(value)
    if spec.is_text_format or spec.kind in (ColumnKind.TEXT, ColumnKind.EMAIL):
        return str(value)
    return value
