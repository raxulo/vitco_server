"""
Prodata Rate-Chart Import Processor Tests (Plan 4.2).

Validates all-or-nothing replace, range bounds, interval overlap, and discarded report.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.prodata_import import ProdataImportProcessor
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import PRODATA_SHEET
from app.modules.dataexchange.infrastructure.prodata_repository import ProdataExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.modules.ratechart.infrastructure.models import ProdataRateRowModel
from tests.dataexchange.factories import (
    create_prodata_chart,
    create_prodata_rows,
    create_user,
    make_context,
)

COLUMNS = PRODATA_SHEET.import_columns()


def _file(path, rows: list[dict]) -> str:
    writer = XlsxSheetWriter(path, PRODATA_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    return path.name


async def _prepare(database, chart_id, tmp_path, rows, *, dry_run=False):
    job_dir = tmp_path / f"job-{uuid4().hex[:6]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    name = _file(job_dir / "source.xlsx", rows)
    user_id = await create_user(database, role=Role.ADMIN)
    return await make_context(
        database,
        kind=ExcelJobKind.PRODATA_IMPORT,
        owner_id=user_id,
        owner_role=Role.ADMIN,
        target_id=chart_id,
        job_dir=job_dir,
        dry_run=dry_run,
        source_file=name,
    )


def _processor(database):
    return ProdataImportProcessor(
        database=database,
        repository=ProdataExchangeRepository(database),
    )


async def test_valid_import_replaces_rows_atomically(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Replace Chart")
    # Initial existing rows (2 rows)
    await create_prodata_rows(database, chart_id, [
        {"row_number": 1, "fat_min": 2.0, "fat_max": 2.9, "fat_rate_per_kg": 300.0},
        {"row_number": 2, "fat_min": 3.0, "fat_max": 3.9, "fat_rate_per_kg": 320.0},
    ])

    new_rows = [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "snf_min": 7.5, "snf_max": 8.5,
         "fat_rate_per_kg": 350.0, "snf_rate_per_kg": 250.0, "snf_cutoff": 7.5, "snf_deduction": 1.5},
        {"row_number": 2, "fat_min": 4.1, "fat_max": 5.0, "snf_min": 8.0, "snf_max": 9.0,
         "fat_rate_per_kg": 370.0, "snf_rate_per_kg": 260.0, "snf_cutoff": 8.0, "snf_deduction": 2.0},
        {"row_number": 3, "fat_min": 5.1, "fat_max": 6.0, "snf_min": 8.5, "snf_max": 9.5,
         "fat_rate_per_kg": 390.0, "snf_rate_per_kg": 270.0, "snf_cutoff": 8.5, "snf_deduction": 2.5},
    ]

    ctx = await _prepare(database, chart_id, tmp_path, new_rows)
    result = await _processor(database).run(ctx)

    assert result.report_file is None
    assert (ctx.inserted, ctx.discarded) == (3, 0)

    # Check database rows replaced
    async with database.transaction() as session:
        stored = (await session.execute(
            select(ProdataRateRowModel)
            .where(ProdataRateRowModel.rate_chart_id == chart_id)
            .order_by(ProdataRateRowModel.row_number.asc())
        )).scalars().all()

    assert len(stored) == 3
    assert [r.row_number for r in stored] == [1, 2, 3]
    assert stored[0].fat_min == 3.0
    assert stored[0].fat_max == 4.0
    assert stored[0].fat_rate_per_kg == 350.0
    assert stored[2].fat_min == 5.1
    assert stored[2].fat_max == 6.0


async def test_dry_run_saves_nothing(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Dry Run Chart")
    await create_prodata_rows(database, chart_id, [
        {"row_number": 1, "fat_min": 2.0, "fat_max": 2.9, "fat_rate_per_kg": 300.0},
    ])

    new_rows = [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "fat_rate_per_kg": 350.0},
        {"row_number": 2, "fat_min": 4.1, "fat_max": 5.0, "fat_rate_per_kg": 370.0},
    ]

    ctx = await _prepare(database, chart_id, tmp_path, new_rows, dry_run=True)
    result = await _processor(database).run(ctx)

    assert result.report_file is None
    assert (ctx.inserted, ctx.discarded) == (2, 0)

    # Database still has only the original 1 row
    async with database.transaction() as session:
        count = await session.scalar(
            select(func.count(ProdataRateRowModel.id))
            .where(ProdataRateRowModel.rate_chart_id == chart_id)
        )
    assert count == 1


async def test_invalid_fat_bounds_rejects_whole_file(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Invalid Bounds Chart")
    await create_prodata_rows(database, chart_id, [
        {"row_number": 1, "fat_min": 2.0, "fat_max": 2.9, "fat_rate_per_kg": 300.0},
    ])

    rows = [
        {"row_number": 1, "fat_min": 4.5, "fat_max": 3.5, "fat_rate_per_kg": 350.0},  # Inverted!
        {"row_number": 2, "fat_min": 5.0, "fat_max": 6.0, "fat_rate_per_kg": 370.0},  # Valid
    ]

    ctx = await _prepare(database, chart_id, tmp_path, rows)
    result = await _processor(database).run(ctx)

    assert result.report_file == "discarded_rows.xlsx"
    assert (ctx.inserted, ctx.discarded) == (0, 1)

    # Database untouched: still has 1 original row
    async with database.transaction() as session:
        count = await session.scalar(
            select(func.count(ProdataRateRowModel.id))
            .where(ProdataRateRowModel.rate_chart_id == chart_id)
        )
    assert count == 1

    # Verify report contents
    report_path = ctx.job_dir / result.report_file
    wb = load_workbook(report_path, read_only=True)
    sheet = wb["Prodata Rate Chart"]
    rows_data = list(sheet.iter_rows(values_only=True))
    assert len(rows_data) == 2  # Header + 1 discarded row
    header = rows_data[0]
    assert header[-2] == "Row No"
    assert header[-1] == "Reason"
    first_discarded = rows_data[1]
    assert first_discarded[-2] == 2  # Excel row 2
    assert "FAT Min (4.5) exceeds FAT Max (3.5)" in first_discarded[-1]
    wb.close()


async def test_invalid_snf_bounds_rejects_whole_file(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Invalid SNF Chart")
    rows = [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "snf_min": 9.5, "snf_max": 8.0},  # Inverted SNF!
    ]
    ctx = await _prepare(database, chart_id, tmp_path, rows)
    result = await _processor(database).run(ctx)

    assert result.report_file is not None
    assert ctx.discarded == 1

    report_path = ctx.job_dir / result.report_file
    wb = load_workbook(report_path, read_only=True)
    sheet = wb["Prodata Rate Chart"]
    rows_data = list(sheet.iter_rows(values_only=True))
    assert "SNF Min (9.5) exceeds SNF Max" in rows_data[1][-1]
    wb.close()


async def test_overlapping_fat_ranges_rejects_whole_file(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Overlap Chart")
    rows = [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.5, "fat_rate_per_kg": 350.0},
        {"row_number": 2, "fat_min": 4.0, "fat_max": 5.0, "fat_rate_per_kg": 370.0},  # Overlaps [3.0, 4.5]!
    ]

    ctx = await _prepare(database, chart_id, tmp_path, rows)
    result = await _processor(database).run(ctx)

    assert result.report_file is not None
    assert (ctx.inserted, ctx.discarded) == (0, 1)

    report_path = ctx.job_dir / result.report_file
    wb = load_workbook(report_path, read_only=True)
    sheet = wb["Prodata Rate Chart"]
    rows_data = list(sheet.iter_rows(values_only=True))
    assert len(rows_data) == 2
    assert "Range overlaps with row 2" in rows_data[1][-1]
    wb.close()


async def test_fat_overlap_allowed_if_snf_does_not_overlap(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="2D Non-overlap Chart")
    rows = [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 5.0, "snf_min": 7.0, "snf_max": 8.0, "fat_rate_per_kg": 350.0},
        {"row_number": 2, "fat_min": 3.0, "fat_max": 5.0, "snf_min": 8.1, "snf_max": 9.5, "fat_rate_per_kg": 370.0},
    ]

    ctx = await _prepare(database, chart_id, tmp_path, rows)
    result = await _processor(database).run(ctx)

    assert result.report_file is None
    assert (ctx.inserted, ctx.discarded) == (2, 0)


async def test_continuous_touching_slabs_allowed(database, tmp_path):
    chart_id = await create_prodata_chart(database, name="Touching Slabs Chart")
    rows = [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "fat_rate_per_kg": 350.0},
        {"row_number": 2, "fat_min": 4.0, "fat_max": 5.0, "fat_rate_per_kg": 370.0},
    ]

    ctx = await _prepare(database, chart_id, tmp_path, rows)
    result = await _processor(database).run(ctx)

    assert result.report_file is None
    assert (ctx.inserted, ctx.discarded) == (2, 0)
