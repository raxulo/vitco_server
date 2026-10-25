"""
Prodata Rate-Chart Export Processor, Sheet Spec and Template Cache (Plan 4.1).
"""

from __future__ import annotations

import pytest
from openpyxl import load_workbook

from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.prodata_export import ProdataExportProcessor
from app.modules.dataexchange.application.templates import prodata_template_path
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import PRODATA_SHEET
from app.modules.dataexchange.infrastructure.prodata_repository import ProdataExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetReader
from tests.dataexchange.factories import (
    create_prodata_chart,
    create_prodata_rows,
    create_user,
    make_context,
)


async def _export(database, chart_id, tmp_path, page_size=1000):
    user_id = await create_user(database, role=Role.ADMIN)
    ctx = await make_context(
        database,
        kind=ExcelJobKind.PRODATA_EXPORT,
        owner_id=user_id,
        owner_role=Role.ADMIN,
        target_id=chart_id,
        job_dir=tmp_path / "job",
    )
    processor = ProdataExportProcessor(
        database=database,
        repository=ProdataExchangeRepository(database),
        page_size=page_size,
    )
    result = await processor.run(ctx)
    return ctx, ctx.job_dir / result.result_file


def _read(path, tmp_path):
    with XlsxSheetReader(path, PRODATA_SHEET, scratch_dir=tmp_path) as reader:
        return [row for batch in reader.iter_batches(1000) for row in batch]


async def test_prodata_template_cached(tmp_path):
    storage_root = tmp_path / "storage"
    path1 = prodata_template_path(storage_root)
    assert path1.is_file()
    mtime1 = path1.stat().st_mtime_ns

    # Second call returns the exact cached file without modifying it
    path2 = prodata_template_path(storage_root)
    assert path1 == path2
    assert path2.stat().st_mtime_ns == mtime1

    wb = load_workbook(path1, read_only=True)
    assert wb.sheetnames == ["Prodata Rate Chart", "Instructions"]
    header = next(wb["Prodata Rate Chart"].iter_rows(min_row=1, max_row=1, values_only=True))
    assert len(header) == 9
    assert header[0] == "Row No"
    assert header[1] == "FAT Min *"
    assert header[2] == "FAT Max *"
    wb.close()


async def test_export_empty_chart(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Empty Chart")
    ctx, path = await _export(database, chart_id, tmp_path)
    assert ctx.total == 0
    assert ctx.processed == 0

    wb = load_workbook(path, read_only=True)
    assert wb.sheetnames == ["Prodata Rate Chart", "Instructions"]
    header = next(wb["Prodata Rate Chart"].iter_rows(min_row=1, max_row=1, values_only=True))
    assert len(header) == 9
    assert sum(1 for _ in wb["Prodata Rate Chart"].iter_rows(min_row=2)) == 0
    wb.close()


async def test_export_multiple_rows_in_order(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Active Chart")
    raw_rows = [
        {"row_number": 2, "fat_min": 4.1, "fat_max": 5.0, "snf_min": 8.1, "snf_max": 9.0,
         "fat_rate_per_kg": 370.0, "snf_rate_per_kg": 260.0, "snf_cutoff": 8.0, "snf_deduction": 2.0},
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "snf_min": 7.5, "snf_max": 8.5,
         "fat_rate_per_kg": 350.0, "snf_rate_per_kg": 250.0, "snf_cutoff": 7.5, "snf_deduction": 1.5},
        {"row_number": 3, "fat_min": 5.1, "fat_max": 6.0, "snf_min": 8.6, "snf_max": 9.5,
         "fat_rate_per_kg": 390.0, "snf_rate_per_kg": 270.0, "snf_cutoff": 8.5, "snf_deduction": 2.5},
    ]
    await create_prodata_rows(database, chart_id, raw_rows)

    ctx, path = await _export(database, chart_id, tmp_path, page_size=2)
    assert ctx.total == 3
    assert ctx.processed == 3

    rows = _read(path, tmp_path)
    assert len(rows) == 3
    # Keyset pagination on row_number ASC ensures order: 1, 2, 3
    assert [r.cells["row_number"] for r in rows] == [1, 2, 3]

    r1 = rows[0].cells
    assert r1["fat_min"] == 3.0
    assert r1["fat_max"] == 4.0
    assert r1["snf_min"] == 7.5
    assert r1["snf_max"] == 8.5
    assert r1["fat_rate_per_kg"] == 350.0
    assert r1["snf_rate_per_kg"] == 250.0
    assert r1["snf_cutoff"] == 7.5
    assert r1["snf_deduction"] == 1.5
