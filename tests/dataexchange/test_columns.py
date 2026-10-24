"""
Column specs, header matching and cell parsing (Plan 1.2, task 1).
"""

from __future__ import annotations

from datetime import datetime, time

import pytest

from app.modules.dataexchange.domain.columns import (
    ColumnKind,
    ColumnSpec,
    HeaderMap,
    Section,
    SheetSpec,
    format_cell,
    normalise_header,
    parse_cell,
)


def _spec(kind: ColumnKind, **extra) -> ColumnSpec:
    return ColumnSpec(key="value", header="Value", section=Section.ENTITY, kind=kind, **extra)


MILK = (("COW", 0), ("BUFFALO", 1), ("MIXED", 2))

SHEET = SheetSpec(
    name="Farmers",
    key_column="farmer_code",
    columns=(
        ColumnSpec(key="farmer_code", header="Farmer Code", section=Section.ENTITY, kind=ColumnKind.CODE, required=True),
        ColumnSpec(key="name", header="Name", section=Section.USER, kind=ColumnKind.TEXT, required=True),
        ColumnSpec(key="mobile", header="Mobile", section=Section.USER, kind=ColumnKind.MOBILE, required=True),
        ColumnSpec(key="milk_type", header="Milk Type", section=Section.ENTITY, kind=ColumnKind.ENUM, choices=MILK),
        ColumnSpec(key="password", header="Password", section=Section.USER, kind=ColumnKind.PASSWORD, import_only=True),
    ),
)


# =========================================================
# HEADERS
# =========================================================

@pytest.mark.parametrize("raw", ["Farmer Code *", "farmer code", "FARMER_CODE", "  Farmer-Code  ", "farmer__code*"])
def test_normalise_header_variants_match(raw):
    assert normalise_header(raw) == "farmer_code"


def test_header_map_handles_reordered_and_unknown_columns():
    header = HeaderMap.build(SHEET, ("Mobile *", "Notes", "farmer_code", "NAME", None, "Milk Type"))

    assert header.is_valid
    assert header.indexes == {"mobile": 0, "farmer_code": 2, "name": 3, "milk_type": 5}
    assert header.unknown == ("Notes",)


def test_header_map_reports_missing_required_headers():
    header = HeaderMap.build(SHEET, ("Farmer Code", "Milk Type"))

    assert not header.is_valid
    assert header.missing_required == ("Name *", "Mobile *")


def test_header_map_keeps_first_duplicate():
    header = HeaderMap.build(SHEET, ("Farmer Code", "Name", "Mobile", "farmer code"))

    assert header.indexes["farmer_code"] == 0
    assert header.duplicates == ("farmer code",)


def test_sheet_export_columns_skip_import_only_password():
    assert "password" not in [column.key for column in SHEET.export_columns()]
    assert "password" in [column.key for column in SHEET.import_columns()]


def test_display_header_marks_required_columns():
    assert SHEET.column("farmer_code").display_header == "Farmer Code *"
    assert SHEET.column("milk_type").display_header == "Milk Type"


# =========================================================
# PARSE — blank
# =========================================================

@pytest.mark.parametrize("raw", [None, "", "   "])
def test_blank_cells_are_blank_not_errors(raw):
    parsed = parse_cell(_spec(ColumnKind.MOBILE), raw)

    assert parsed.blank and parsed.error is None and parsed.value is None


# =========================================================
# PARSE — each kind: good and bad
# =========================================================

@pytest.mark.parametrize(
    ("kind", "extra", "raw", "expected"),
    [
        (ColumnKind.TEXT, {}, "  Ram Singh ", "Ram Singh"),
        (ColumnKind.TEXT, {}, 12.5, "12.5"),
        (ColumnKind.CODE, {}, 101.0, "101"),
        (ColumnKind.CODE, {}, "F-001", "F-001"),
        (ColumnKind.INT, {"min_value": 1}, "3", 3),
        (ColumnKind.INT, {}, 4.0, 4),
        (ColumnKind.FLOAT, {"max_value": 15}, "6.5", 6.5),
        (ColumnKind.BOOL, {}, "yes", True),
        (ColumnKind.BOOL, {}, "N", False),
        (ColumnKind.BOOL, {}, True, True),
        (ColumnKind.BOOL, {}, 0, False),
        (ColumnKind.ENUM, {"choices": MILK}, "buffalo", 1),
        (ColumnKind.ENUM, {"choices": MILK}, 2, 2),
        (ColumnKind.ENUM, {"choices": MILK}, "0", 0),
        (ColumnKind.EMAIL, {}, " Ram@Example.COM ", "ram@example.com"),
        (ColumnKind.MOBILE, {}, 9876543210, "9876543210"),
        (ColumnKind.MOBILE, {}, 9876543210.0, "9876543210"),
        (ColumnKind.MOBILE, {}, "+91 98765-43210", "9876543210"),
        (ColumnKind.TIME, {}, "6:05", "06:05"),
        (ColumnKind.TIME, {}, time(18, 30), "18:30"),
        (ColumnKind.TIME, {}, datetime(2026, 1, 1, 7, 0), "07:00"),
        (ColumnKind.TIME, {}, 0.25, "06:00"),
        (ColumnKind.TIME, {}, 0.8125, "19:30"),
        (ColumnKind.PINCODE, {}, 452001, "452001"),
        (ColumnKind.ACCOUNT_NUMBER, {}, "1234 5678 9012 3456", "1234567890123456"),
        (ColumnKind.IFSC, {}, "sbin0001234", "SBIN0001234"),
        (ColumnKind.PASSWORD, {"min_length": 8}, "Secret@123", "Secret@123"),
    ],
)
def test_parse_accepts_valid_values(kind, extra, raw, expected):
    parsed = parse_cell(_spec(kind, **extra), raw)

    assert parsed.error is None
    assert parsed.value == expected


@pytest.mark.parametrize(
    ("kind", "extra", "raw", "message"),
    [
        (ColumnKind.TEXT, {"max_length": 5}, "too long text", "at most 5 characters"),
        (ColumnKind.CODE, {}, 101.5, "must not contain decimals"),
        (ColumnKind.INT, {}, "3.5", "whole number"),
        (ColumnKind.INT, {"min_value": 1}, 0, "at least 1"),
        (ColumnKind.FLOAT, {}, "abc", "must be a number"),
        (ColumnKind.FLOAT, {"max_value": 15}, 16, "at most 15"),
        (ColumnKind.BOOL, {}, "maybe", "YES or NO"),
        (ColumnKind.ENUM, {"choices": MILK}, "GOAT", "one of: COW, BUFFALO, MIXED"),
        (ColumnKind.EMAIL, {}, "not-an-email", "valid email"),
        (ColumnKind.MOBILE, {}, "12345", "exactly 10 digits"),
        (ColumnKind.MOBILE, {}, 98765.5, "exactly 10 digits"),
        (ColumnKind.TIME, {}, "25:00", "time like 06:30"),
        (ColumnKind.TIME, {}, 1.5, "time like 06:30"),
        (ColumnKind.PINCODE, {}, "04520", "6-digit pincode"),
        (ColumnKind.ACCOUNT_NUMBER, {}, "12AB", "6 to 20 digits"),
        (ColumnKind.IFSC, {}, "SBIN1234", "IFSC"),
        (ColumnKind.PASSWORD, {"min_length": 8}, "short", "at least 8 characters"),
    ],
)
def test_parse_rejects_invalid_values_with_readable_message(kind, extra, raw, message):
    parsed = parse_cell(_spec(kind, **extra), raw)

    assert parsed.value is None
    assert parsed.error is not None
    assert parsed.error.startswith("Value: ")
    assert message in parsed.error


# =========================================================
# FORMAT -> PARSE round trip
# =========================================================

@pytest.mark.parametrize(
    ("kind", "extra", "value", "excel"),
    [
        (ColumnKind.TEXT, {}, "Ram", "Ram"),
        (ColumnKind.CODE, {}, "F001", "F001"),
        (ColumnKind.INT, {}, 7, 7),
        (ColumnKind.FLOAT, {}, 3.25, 3.25),
        (ColumnKind.BOOL, {}, True, "YES"),
        (ColumnKind.BOOL, {}, False, "NO"),
        (ColumnKind.ENUM, {"choices": MILK}, 1, "BUFFALO"),
        (ColumnKind.EMAIL, {}, "a@b.in", "a@b.in"),
        (ColumnKind.MOBILE, {}, "9876543210", "9876543210"),
        (ColumnKind.TIME, {}, "06:00", "06:00"),
        (ColumnKind.PINCODE, {}, "452001", "452001"),
        (ColumnKind.ACCOUNT_NUMBER, {}, "123456789012345678", "123456789012345678"),
        (ColumnKind.IFSC, {}, "HDFC0000001", "HDFC0000001"),
    ],
)
def test_format_then_parse_round_trips(kind, extra, value, excel):
    spec = _spec(kind, **extra)

    formatted = format_cell(spec, value)
    parsed = parse_cell(spec, formatted)

    assert formatted == excel
    assert parsed.error is None
    assert parsed.value == value


def test_format_none_is_empty_cell():
    assert format_cell(_spec(ColumnKind.MOBILE), None) is None


def test_text_format_kinds_and_dropdowns():
    assert _spec(ColumnKind.MOBILE).is_text_format
    assert _spec(ColumnKind.ACCOUNT_NUMBER).is_text_format
    assert not _spec(ColumnKind.FLOAT).is_text_format
    assert _spec(ColumnKind.BOOL).dropdown == ("YES", "NO")
    assert _spec(ColumnKind.ENUM, choices=MILK).dropdown == ("COW", "BUFFALO", "MIXED")
    assert _spec(ColumnKind.TEXT).dropdown == ()
