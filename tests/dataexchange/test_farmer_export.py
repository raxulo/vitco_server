"""
Farmer export processor, sheet spec, email index and template cache (Plan 2.1).
"""

from __future__ import annotations

import os

from openpyxl import load_workbook
from sqlalchemy import text

from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.farmer_export import FarmerExportProcessor
from app.modules.dataexchange.application.templates import template_path
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import FARMER_SHEET
from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.indexes import ensure_indexes
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetReader
from tests.dataexchange.factories import create_farmers, create_vlcc, make_context


async def _export(database, vlcc, tmp_path, page_size=1000):
    ctx = await make_context(database, kind=ExcelJobKind.FARMER_EXPORT, owner_id=vlcc.user_id,
                             owner_role=Role.VLCC, target_id=vlcc.id, job_dir=tmp_path / "job")
    processor = FarmerExportProcessor(database=database, repository=FarmerExchangeRepository(database), page_size=page_size)
    result = await processor.run(ctx)
    return ctx, ctx.job_dir / result.result_file


def _read(path, tmp_path):
    with XlsxSheetReader(path, FARMER_SHEET, scratch_dir=tmp_path) as reader:
        return [row for batch in reader.iter_batches(1000) for row in batch]


async def test_export_writes_only_this_vlccs_farmers_in_code_order(database, tmp_path):
    vlcc_a = await create_vlcc(database)
    vlcc_b = await create_vlcc(database)
    farmers_a = await create_farmers(database, vlcc_a, 2500, prefix="A")
    await create_farmers(database, vlcc_b, 3, prefix="B")
    await create_farmers(database, vlcc_a, 2, prefix="Z", deleted=True)

    ctx, path = await _export(database, vlcc_a, tmp_path)
    rows = _read(path, tmp_path)

    assert ctx.total == ctx.processed == 2500
    assert [row.cells["farmer_code"] for row in rows] == [farmer["farmer_code"] for farmer in farmers_a]
    first, expected = rows[0].cells, farmers_a[0]
    assert first["name"] == expected["name"]
    assert first["mobile"] == expected["mobile"]                 # text, not 9.87E+09
    assert first["email"] == expected["email"]
    assert first["account_number"] == expected["account_number"]  # 16 digits intact
    assert (first["milk_type"], first["assigned_chart_rank"], first["sms_enabled"], first["is_active"]) == ("COW", 2, "YES", "YES")
    assert (first["address_line"], first["city"], first["pincode"], first["ifsc_code"]) == ("Main Road", "Indore", "452001", "SBIN0001234")


async def test_farmer_without_address_and_bank_exports_blank_cells(database, tmp_path):
    vlcc = await create_vlcc(database)
    await create_farmers(database, vlcc, 1, with_address=False, with_bank=False)

    _, path = await _export(database, vlcc, tmp_path)
    cells = _read(path, tmp_path)[0].cells

    assert cells["address_line"] is None and cells["pincode"] is None
    assert cells["account_holder"] is None and cells["account_number"] is None


async def test_export_file_layout_has_no_password_and_an_instructions_sheet(database, tmp_path):
    vlcc = await create_vlcc(database)
    await create_farmers(database, vlcc, 3)

    _, path = await _export(database, vlcc, tmp_path, page_size=2)        # 2 pages
    book = load_workbook(path, read_only=True)
    header = next(book["Farmers"].iter_rows(min_row=1, max_row=1, values_only=True))

    assert book.sheetnames == ["Farmers", "Instructions"]
    assert "Password" not in header
    assert header[:3] == ("Farmer Code *", "Milk Type", "Rate Chart Rank")
    assert sum(1 for _ in book["Farmers"].iter_rows(min_row=2)) == 3


async def test_empty_vlcc_exports_a_header_only_file(database, tmp_path):
    vlcc = await create_vlcc(database)

    ctx, path = await _export(database, vlcc, tmp_path)

    assert ctx.total == ctx.processed == 0
    assert _read(path, tmp_path) == []


async def test_ensure_indexes_is_idempotent(database):
    await ensure_indexes(database)
    await ensure_indexes(database)

    async with database.transaction() as session:
        names = [row[1] for row in (await session.execute(text("PRAGMA index_list(users)"))).all()]
        plan = (await session.execute(text("EXPLAIN QUERY PLAN SELECT id FROM users WHERE lower(email) IN ('a@b.c')"))).all()

    assert names.count("ix_users_email_lower") == 1
    assert "ix_users_email_lower" in plan[0][-1]


def test_template_is_built_once_and_reused(tmp_path):
    first = template_path(tmp_path, FARMER_SHEET, "farmers")
    stamp = os.stat(first).st_mtime_ns
    second = template_path(tmp_path, FARMER_SHEET, "farmers")

    assert first == second and os.stat(second).st_mtime_ns == stamp
    book = load_workbook(first, read_only=True)
    assert book.sheetnames == ["Farmers", "Instructions"]
    assert sum(1 for _ in book["Farmers"].iter_rows(min_row=2)) == 0
    header = next(book["Farmers"].iter_rows(max_row=1, values_only=True))
    assert "Password" in header                         # templates are for importing
