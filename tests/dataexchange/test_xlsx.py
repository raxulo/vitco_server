"""
Streaming xlsx writer / reader (Plan 1.2, task 2; DECISION-012).

Files come from three independent sources so the reader is not only tested
against its own writer: our xlsxwriter-based writer, openpyxl (which, like
Excel, stores text in sharedStrings.xml) and hand-built XML parts.
"""

from __future__ import annotations

import time
import tracemalloc
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app.modules.dataexchange.domain.columns import ColumnKind, ColumnSpec, Section, SheetSpec
from app.modules.dataexchange.domain.exceptions import InvalidExcelFileException
from app.modules.dataexchange.infrastructure.xlsx import ExtraColumn, XlsxSheetReader, XlsxSheetWriter

MILK = (("COW", 0), ("BUFFALO", 1), ("MIXED", 2))

SHEET = SheetSpec(
    name="Farmers",
    key_column="farmer_code",
    columns=(
        ColumnSpec(key="farmer_code", header="Farmer Code", section=Section.ENTITY, kind=ColumnKind.CODE, required=True),
        ColumnSpec(key="name", header="Name", section=Section.USER, kind=ColumnKind.TEXT, required=True),
        ColumnSpec(key="mobile", header="Mobile", section=Section.USER, kind=ColumnKind.MOBILE, required=True),
        ColumnSpec(key="milk_type", header="Milk Type", section=Section.ENTITY, kind=ColumnKind.ENUM, choices=MILK),
        ColumnSpec(key="sms", header="SMS Enabled", section=Section.ENTITY, kind=ColumnKind.BOOL),
        ColumnSpec(key="account", header="Account Number", section=Section.BANK, kind=ColumnKind.ACCOUNT_NUMBER),
        ColumnSpec(key="password", header="Password", section=Section.USER, kind=ColumnKind.PASSWORD, import_only=True),
    ),
)


def _write(path: Path, rows, **options) -> XlsxSheetWriter:
    writer = XlsxSheetWriter(path, SHEET, tmpdir=path.parent, **options)
    writer.write_rows(rows)
    writer.write_instructions()
    writer.close()
    return writer


def _read_all(path: Path, scratch: Path, **options) -> list:
    with XlsxSheetReader(path, SHEET, scratch_dir=scratch, **options) as reader:
        return [row for batch in reader.iter_batches(250) for row in batch]


def _row(i: int) -> list:
    return [f"F{i:05d}", f"Farmer {i}", f"98{i:08d}", "COW", "YES", "1234567890123456"]


def _build_xlsx(path: Path, sheet_xml: str, shared: list[str] | None = None) -> None:
    """Minimal hand-built workbook: lets tests control the exact XML the reader sees."""
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>'
        '</Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Farmers" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="x"/>')
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        if shared is not None:
            items = "".join(f"<si><t>{text}</t></si>" for text in shared)
            archive.writestr("xl/sharedStrings.xml", f'<?xml version="1.0"?><sst xmlns="x">{items}</sst>')


HEADER_XML = (
    '<row r="1"><c r="A1" t="inlineStr"><is><t>Farmer Code</t></is></c>'
    '<c r="B1" t="inlineStr"><is><t>Name</t></is></c>'
    '<c r="C1" t="inlineStr"><is><t>Mobile</t></is></c>'
    '<c r="D1" t="inlineStr"><is><t>SMS Enabled</t></is></c></row>'
)


def _sheet_xml(rows: str, *, prolog: str = "") -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>{prolog}'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{HEADER_XML}{rows}</sheetData></worksheet>'
    )


# =========================================================
# WRITER
# =========================================================

def test_writer_formats_header_dropdowns_text_columns_and_instructions(tmp_path):
    path = tmp_path / "farmers.xlsx"
    _write(path, [_row(1)])

    book = load_workbook(path)
    sheet = book["Farmers"]

    assert book.sheetnames == ["Farmers", "Instructions"]
    assert [cell.value for cell in sheet[1]] == [
        "Farmer Code *", "Name *", "Mobile *", "Milk Type", "SMS Enabled", "Account Number",
    ]                                                         # password is import-only
    assert sheet.freeze_panes == "A2"
    assert sheet.auto_filter.ref == "A1:F1"
    assert sheet["A1"].font.b is True
    assert sheet["A1"].fill.fgColor.rgb.endswith(Section.ENTITY.fill)
    assert sheet["B1"].fill.fgColor.rgb.endswith(Section.USER.fill)
    assert sheet["C2"].number_format == "@"                   # mobile stored as text
    assert sheet["F2"].number_format == "@"
    lists = sorted(str(validation.formula1) for validation in sheet.data_validations.dataValidation)
    assert lists == ['"COW,BUFFALO,MIXED"', '"YES,NO"']

    notes = book["Instructions"]
    assert [cell.value for cell in notes[1]][:4] == ["Column", "Section", "Required", "Type"]
    password_row = next(row for row in notes.iter_rows(values_only=True) if row[0] == "Password")
    assert "Import only" in password_row[6]


def test_writer_extra_report_columns(tmp_path):
    path = tmp_path / "report.xlsx"
    writer = XlsxSheetWriter(path, SHEET, extra_columns=(ExtraColumn("Row No"), ExtraColumn("Reason", 50)))
    writer.write_rows([_row(1) + [17, "Mobile repeats row 3"]])
    writer.close()

    sheet = load_workbook(path)["Farmers"]
    assert [cell.value for cell in sheet[1]][-2:] == ["Row No", "Reason"]
    assert [cell.value for cell in sheet[2]][-2:] == [17, "Mobile repeats row 3"]


def test_writer_moves_long_dropdowns_to_hidden_lists_sheet(tmp_path):
    choices = tuple((f"VERY LONG CHOICE NUMBER {i:03d}", i) for i in range(40))
    sheet_spec = SheetSpec(name="Wide", key_column="code", columns=(
        ColumnSpec(key="code", header="Code", section=Section.ENTITY, kind=ColumnKind.CODE, required=True),
        ColumnSpec(key="kind", header="Kind", section=Section.ENTITY, kind=ColumnKind.ENUM, choices=choices),
    ))
    path = tmp_path / "wide.xlsx"
    writer = XlsxSheetWriter(path, sheet_spec)
    writer.write_rows([["A", "VERY LONG CHOICE NUMBER 001"]])
    writer.close()

    book = load_workbook(path)
    assert book["Lists"].sheet_state == "hidden"
    assert book["Lists"]["A40"].value == "VERY LONG CHOICE NUMBER 039"
    formula = book["Wide"].data_validations.dataValidation[0].formula1
    assert formula == "Lists!$A$1:$A$40"


# =========================================================
# ROUND TRIP
# =========================================================

def test_round_trip_keeps_long_numbers_and_mobile_as_text(tmp_path):
    path = tmp_path / "farmers.xlsx"
    _write(path, [_row(7)])

    rows = _read_all(path, tmp_path)

    assert len(rows) == 1
    assert rows[0].sheet == "Farmers" and rows[0].row_no == 2
    assert rows[0].cells["mobile"] == "9800000007"
    assert rows[0].cells["account"] == "1234567890123456"
    assert rows[0].cells["sms"] == "YES"


def _shared_cell(ref: str, index: int) -> str:
    return f'<c r="{ref}" t="s"><v>{index}</v></c>'


def test_reader_handles_reordered_and_unknown_columns_with_shared_strings(tmp_path):
    # Excel stores text in sharedStrings.xml (openpyxl 3.1.5 writes inline strings only),
    # so this workbook is built by hand the way Excel saves it.
    shared = ["Notes", "mobile", "FARMER CODE *", "name", "x", "F1", "Ram", "y", "9876500000", "Shyam"]
    rows = (
        '<row r="1">' + "".join(_shared_cell(f"{col}1", i) for i, col in enumerate("ABCD")) + "</row>"
        f'<row r="2">{_shared_cell("A2", 4)}<c r="B2"><v>9876543210</v></c>{_shared_cell("C2", 5)}{_shared_cell("D2", 6)}</row>'
        f'<row r="3">{_shared_cell("A3", 7)}{_shared_cell("B3", 8)}<c r="C3"><v>102</v></c>{_shared_cell("D3", 9)}</row>'
    )
    path = tmp_path / "excel-style.xlsx"
    _build_xlsx(path, '<?xml version="1.0"?><worksheet xmlns="x"><sheetData>' + rows + "</sheetData></worksheet>",
                shared=shared)

    result = _read_all(path, tmp_path)

    assert [row.cells for row in result] == [
        {"mobile": 9876543210, "farmer_code": "F1", "name": "Ram"},
        {"mobile": "9876500000", "farmer_code": 102, "name": "Shyam"},
    ]


def test_shared_strings_spill_to_disk_and_resolve_correctly(tmp_path):
    shared = ["Farmer Code", "Name", "Mobile"]
    rows = ['<row r="1">' + "".join(_shared_cell(f"{col}1", i) for i, col in enumerate("ABC")) + "</row>"]
    for i in range(300):
        base = len(shared)
        shared += [f"F{i}", f"Unique Name {i}", f"98{i:08d}"]
        rows.append(f'<row r="{i + 2}">' + "".join(
            _shared_cell(f"{col}{i + 2}", base + offset) for offset, col in enumerate("ABC")
        ) + "</row>")
    path = tmp_path / "many-strings.xlsx"
    _build_xlsx(path, '<?xml version="1.0"?><worksheet xmlns="x"><sheetData>' + "".join(rows) + "</sheetData></worksheet>",
                shared=shared)

    with XlsxSheetReader(path, SHEET, scratch_dir=tmp_path, memory_strings=50) as reader:
        assert (tmp_path / "shared_strings.bin").exists()
        assert (tmp_path / "shared_strings.idx").exists()
        rows = [row for batch in reader.iter_batches(64) for row in batch]

    assert len(rows) == 300
    assert rows[299].cells == {"farmer_code": "F299", "name": "Unique Name 299", "mobile": "9800000299"}
    assert not (tmp_path / "shared_strings.bin").exists()         # scratch files removed on close
    assert not (tmp_path / "shared_strings.idx").exists()


def test_reader_parses_cell_types_formulas_rich_text_and_gaps(tmp_path):
    path = tmp_path / "types.xlsx"
    rows = (
        '<row r="2"><c r="A2" t="s"><v>0</v></c>'
        '<c r="B2" t="inlineStr"><is><r><t>Ram </t></r><r><t>Singh</t></r></is></c>'
        '<c r="C2"><v>9876543210</v></c><c r="D2" t="b"><v>1</v></c></row>'
        '<row r="3"><c r="A3" t="str"><f>CONCAT("F","2")</f><v>F2</v></c>'
        '<c r="C3"><v>9.87654321E9</v></c><c r="D3" t="b"><v>0</v></c></row>'
        '<row><c t="inlineStr"><is><t>F3</t></is></c><c t="inlineStr"><is><t>No Refs</t></is></c></row>'
    )
    _build_xlsx(path, _sheet_xml(rows), shared=["F1"])

    result = _read_all(path, tmp_path)

    assert [row.row_no for row in result] == [2, 3, 4]
    assert result[0].cells == {"farmer_code": "F1", "name": "Ram Singh", "mobile": 9876543210, "sms": True}
    assert result[1].cells == {"farmer_code": "F2", "name": None, "mobile": 9876543210.0, "sms": False}
    assert result[2].cells["farmer_code"] == "F3" and result[2].cells["name"] == "No Refs"


# =========================================================
# LIMITS
# =========================================================

def test_export_splits_into_numbered_sheets_and_reader_reads_them_all(tmp_path):
    path = tmp_path / "split.xlsx"
    writer = _write(path, (_row(i) for i in range(2500)), rows_per_sheet=1000)

    assert writer.sheet_count == 3 and writer.rows_written == 2500
    assert load_workbook(path, read_only=True).sheetnames == ["Farmers", "Farmers (2)", "Farmers (3)", "Instructions"]

    with XlsxSheetReader(path, SHEET, scratch_dir=tmp_path) as reader:
        assert reader.sheet_names == ["Farmers", "Farmers (2)", "Farmers (3)"]   # Instructions skipped
        assert reader.estimated_rows == 2500
        rows = [row for batch in reader.iter_batches(400) for row in batch]

    assert len(rows) == 2500
    assert [row.cells["farmer_code"] for row in rows] == [f"F{i:05d}" for i in range(2500)]
    assert (rows[999].sheet, rows[999].row_no) == ("Farmers", 1001)
    assert (rows[1000].sheet, rows[1000].row_no) == ("Farmers (2)", 2)
    assert (rows[2499].sheet, rows[2499].row_no) == ("Farmers (3)", 501)


def test_reader_stops_after_long_run_of_empty_rows(tmp_path):
    path = tmp_path / "padded.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Farmers"
    sheet.append(["Farmer Code", "Name", "Mobile"])
    for i in range(10):
        sheet.append([f"F{i}", "Ram", "9876543210"])
    for row in range(12, 50):                     # formatted but empty cells
        sheet.cell(row=row, column=1, value="")
    sheet.cell(row=1512, column=1, value="AFTER-GAP")
    book.save(path)

    rows = _read_all(path, tmp_path, max_empty_run=1000)

    assert [row.cells["farmer_code"] for row in rows] == [f"F{i}" for i in range(10)]


def test_reader_rejects_more_than_max_rows(tmp_path):
    path = tmp_path / "big.xlsx"
    _write(path, (_row(i) for i in range(30)))

    with pytest.raises(InvalidExcelFileException, match="more than 25 rows"):
        _read_all(path, tmp_path, max_rows=25)


def test_reader_reports_missing_required_headers(tmp_path):
    path = tmp_path / "bad-header.xlsx"
    book = Workbook()
    book.active.append(["Farmer Code", "Notes"])
    book.save(path)

    with pytest.raises(InvalidExcelFileException, match=r"Name \*, Mobile \*"):
        _read_all(path, tmp_path)


# =========================================================
# HOSTILE / DAMAGED FILES
# =========================================================

def test_reader_refuses_xml_entity_declarations(tmp_path):
    path = tmp_path / "bomb.xlsx"
    prolog = '<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>'
    _build_xlsx(path, _sheet_xml('<row r="2"><c r="A2" t="inlineStr"><is><t>&lol2;</t></is></c></row>', prolog=prolog))

    with pytest.raises(InvalidExcelFileException, match="not allowed"):
        _read_all(path, tmp_path)


def test_reader_rejects_damaged_xml_and_non_zip(tmp_path):
    damaged = tmp_path / "damaged.xlsx"
    _build_xlsx(damaged, _sheet_xml('<row r="2"><c r="A2"><v>1</v></row>'))       # unclosed <c>
    not_zip = tmp_path / "fake.xlsx"
    not_zip.write_text("hello")

    with pytest.raises(InvalidExcelFileException, match="damaged"):
        _read_all(damaged, tmp_path)
    with pytest.raises(InvalidExcelFileException, match="Not a valid .xlsx"):
        _read_all(not_zip, tmp_path)


def test_reader_rejects_oversized_cell(tmp_path):
    path = tmp_path / "huge-cell.xlsx"
    _build_xlsx(path, _sheet_xml(f'<row r="2"><c r="A2" t="inlineStr"><is><t>{"x" * 40_000}</t></is></c></row>'))

    with pytest.raises(InvalidExcelFileException, match="longer than Excel allows"):
        _read_all(path, tmp_path)


# =========================================================
# STREAMING (NFR-01)
# =========================================================

def test_100k_row_round_trip_has_flat_memory(tmp_path):
    path = tmp_path / "100k.xlsx"
    rows = 100_000

    tracemalloc.start()
    started = time.perf_counter()
    _write(path, (_row(i) for i in range(rows)))
    _, write_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()

    count = 0
    with XlsxSheetReader(path, SHEET, scratch_dir=tmp_path) as reader:
        for batch in reader.iter_batches(500):
            count += len(batch)
    _, read_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    elapsed = time.perf_counter() - started

    print(f"\n100k round trip: {elapsed:.1f}s, write peak {write_peak / 1e6:.1f} MB, read peak {read_peak / 1e6:.1f} MB")
    assert count == rows
    assert write_peak < 60e6
    assert read_peak < 60e6
