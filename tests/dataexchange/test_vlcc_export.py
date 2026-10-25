"""
VLCC export processor, sheet spec and template cache (Plan 3.1).
"""

from __future__ import annotations

from openpyxl import load_workbook

from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.templates import vlcc_template_path
from app.modules.dataexchange.application.vlcc_export import VlccExportProcessor
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import VLCC_SHEET
from app.modules.dataexchange.infrastructure.vlcc_repository import VlccExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetReader
from tests.dataexchange.factories import create_full_vlccs, create_user, make_context


async def _export(database, owner_id, tmp_path, page_size=1000):
    ctx = await make_context(
        database,
        kind=ExcelJobKind.VLCC_EXPORT,
        owner_id=owner_id,
        owner_role=Role.ADMIN,
        target_id=owner_id,
        job_dir=tmp_path / "job",
    )
    processor = VlccExportProcessor(
        database=database,
        repository=VlccExchangeRepository(database),
        page_size=page_size,
    )
    result = await processor.run(ctx)
    return ctx, ctx.job_dir / result.result_file


def _read(path, tmp_path):
    with XlsxSheetReader(path, VLCC_SHEET, scratch_dir=tmp_path) as reader:
        return [row for batch in reader.iter_batches(1000) for row in batch]


async def test_export_writes_only_this_owners_vlccs_in_code_order(database, tmp_path):
    owner_a = await create_user(database, role=Role.ADMIN, name="Admin A")
    owner_b = await create_user(database, role=Role.ADMIN, name="Admin B")

    vlccs_a = await create_full_vlccs(database, owner_a, 5, prefix="A")
    await create_full_vlccs(database, owner_b, 2, prefix="B")
    await create_full_vlccs(database, owner_a, 1, prefix="Z", deleted=True)

    ctx, path = await _export(database, owner_a, tmp_path)
    rows = _read(path, tmp_path)

    assert ctx.total == ctx.processed == 5
    assert [row.cells["vlcc_code"] for row in rows] == [v["vlcc_code"] for v in vlccs_a]

    first, expected = rows[0].cells, vlccs_a[0]
    assert first["vlcc_name"] == expected["vlcc_name"]
    assert first["uic_code"] == expected["uic_code"]
    assert first["user_name"] == expected["user_name"]
    assert first["mobile"] == expected["mobile"]
    assert first["address_line"] == "Station Road"
    assert first["city"] == "Ujjain"
    assert first["pincode"] == "456001"
    assert first["bank_name"] == "HDFC"
    assert first["account_number"] == expected["account_number"]
    assert first["analyzer_type"] == "TYPE_A"
    assert first["weight_unit"] == "LITER"
    assert first["receipt_size"] == "SMALL"
    assert first["cow_min_fat"] == 2.5
    assert first["buffalo_max_snf"] == 15.0


async def test_vlcc_without_relations_exports_blank_cells(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)
    await create_full_vlccs(database, owner, 1, with_relations=False)

    _, path = await _export(database, owner, tmp_path)
    cells = _read(path, tmp_path)[0].cells

    assert cells["address_line"] is None and cells["city"] is None
    assert cells["bank_name"] is None and cells["account_number"] is None
    assert cells["analyzer_type"] is None
    assert cells["cow_min_fat"] is None


async def test_export_file_layout_has_no_password_and_an_instructions_sheet(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)
    await create_full_vlccs(database, owner, 3)

    _, path = await _export(database, owner, tmp_path, page_size=2)
    book = load_workbook(path, read_only=True)
    header = next(book["VLCCs"].iter_rows(min_row=1, max_row=1, values_only=True))

    assert book.sheetnames == ["VLCCs", "Instructions"]
    assert "Password" not in header
    assert len(header) == 43  # 44 total - 1 import-only password
    assert header[0] == "VLCC Code *"
    assert header[1] == "UIC Code *"
    assert header[2] == "VLCC Name *"
    assert sum(1 for _ in book["VLCCs"].iter_rows(min_row=2)) == 3


async def test_empty_owner_exports_header_only_file(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)

    ctx, path = await _export(database, owner, tmp_path)

    assert ctx.total == ctx.processed == 0
    assert _read(path, tmp_path) == []


async def test_vlcc_template_cached(tmp_path):
    path1 = vlcc_template_path(tmp_path)
    assert path1.is_file()

    mtime1 = path1.stat().st_mtime
    path2 = vlcc_template_path(tmp_path)
    assert path1 == path2
    assert path2.stat().st_mtime == mtime1

    book = load_workbook(path1, read_only=True)
    assert book.sheetnames == ["VLCCs", "Instructions"]
    header = next(book["VLCCs"].iter_rows(min_row=1, max_row=1, values_only=True))
    assert len(header) == 44  # Template includes Password
    assert "Password" in header
