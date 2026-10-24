"""
FileGuard (Plan 1.3, task 2). Every file is built for real under tmp_path.
"""

from __future__ import annotations

import zipfile

import pytest

from app.modules.dataexchange.domain.columns import ColumnKind, ColumnSpec, Section, SheetSpec
from app.modules.dataexchange.domain.exceptions import InvalidExcelFileException
from app.modules.dataexchange.infrastructure.file_guard import FileGuard
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter

GUARD = FileGuard(max_uncompressed_bytes=200 * 1024 * 1024)
SHEET = SheetSpec(name="Farmers", key_column="code", columns=(
    ColumnSpec(key="code", header="Code", section=Section.ENTITY, kind=ColumnKind.CODE, required=True),
))


def _zip(path, parts: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in parts.items():
            archive.writestr(name, data)


BASE_PARTS = {
    "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
    "xl/workbook.xml": b'<?xml version="1.0"?><workbook/>',
}


def test_real_workbook_passes(tmp_path):
    path = tmp_path / "ok.xlsx"
    writer = XlsxSheetWriter(path, SHEET)
    writer.write_rows([["F1"], ["F2"]])
    writer.close()

    GUARD.inspect(path)                                     # no exception


def test_text_file_is_rejected(tmp_path):
    path = tmp_path / "notes.xlsx"
    path.write_text("name,mobile\nRam,9876543210\n")

    with pytest.raises(InvalidExcelFileException, match="Not an .xlsx file"):
        GUARD.inspect(path)


def test_zip_without_workbook_is_rejected(tmp_path):
    path = tmp_path / "photos.xlsx"
    _zip(path, {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<doc/>"})

    with pytest.raises(InvalidExcelFileException, match="Not an Excel workbook"):
        GUARD.inspect(path)


def test_highly_compressed_member_is_rejected(tmp_path):
    path = tmp_path / "bomb.xlsx"
    _zip(path, {**BASE_PARTS, "xl/worksheets/sheet1.xml": b"\0" * (50 * 1024 * 1024)})   # ~1000:1

    with pytest.raises(InvalidExcelFileException, match="compressed suspiciously well"):
        GUARD.inspect(path)


def test_total_uncompressed_limit(tmp_path):
    path = tmp_path / "huge.xlsx"
    _zip(path, {**BASE_PARTS, "xl/media/a.bin": bytes(range(256)) * 4096})               # 1 MB, poorly compressible

    with pytest.raises(InvalidExcelFileException, match="too large once uncompressed"):
        FileGuard(max_uncompressed_bytes=512 * 1024).inspect(path)


def test_too_many_members_is_rejected(tmp_path):
    path = tmp_path / "many.xlsx"
    _zip(path, {**BASE_PARTS, **{f"xl/x/{i}.xml": b"<a/>" for i in range(30)}})

    with pytest.raises(InvalidExcelFileException, match="too many parts"):
        FileGuard(max_uncompressed_bytes=10 ** 9, max_members=20).inspect(path)


@pytest.mark.parametrize("declaration", [b"<!DOCTYPE x>", b"<!ENTITY lol 'lol'>", b"<! doctype x>"])
def test_xml_declarations_are_rejected(tmp_path, declaration):
    path = tmp_path / "entities.xlsx"
    _zip(path, {**BASE_PARTS, "xl/sharedStrings.xml": b'<?xml version="1.0"?>' + declaration + b"<sst/>"})

    with pytest.raises(InvalidExcelFileException, match="declarations that are not allowed"):
        GUARD.inspect(path)


def test_unsafe_member_path_is_rejected(tmp_path):
    path = tmp_path / "slip.xlsx"
    _zip(path, {**BASE_PARTS, "../../evil.xml": b"<a/>"})

    with pytest.raises(InvalidExcelFileException, match="unsafe path"):
        GUARD.inspect(path)


def test_damaged_zip_is_rejected(tmp_path):
    path = tmp_path / "cut.xlsx"
    _zip(path, BASE_PARTS)
    path.write_bytes(path.read_bytes()[:40])               # keep the magic bytes, cut the directory

    with pytest.raises(InvalidExcelFileException, match="damaged"):
        GUARD.inspect(path)
