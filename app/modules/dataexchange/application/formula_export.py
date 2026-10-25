"""
Formula Rate-Chart Export Processor

Writes formula configuration parameters and an optional calculated
pricing preview into an Excel workbook (REQ-20).

Python 3.13+
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.modules.dataexchange.application.processor import JobContext, ProcessorResult
from app.modules.dataexchange.domain.columns import format_cell
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import FORMULA_SHEET
from app.modules.dataexchange.infrastructure.formula_repository import FormulaExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.modules.ratechart.domain.enums import MilkType

_RESULT_FILE = "result.xlsx"


class FormulaExportProcessor:

    __slots__ = ("_database", "_repository", "_columns")

    kind = ExcelJobKind.FORMULA_EXPORT

    def __init__(self, *, database: DatabaseManager, repository: FormulaExchangeRepository) -> None:
        self._database = database
        self._repository = repository
        self._columns = FORMULA_SHEET.export_columns()

    async def run(self, ctx: JobContext) -> ProcessorResult:
        chart_id = ctx.job.target_id
        if chart_id is None:
            raise ValueError("No rate chart selected for this export")

        async with self._database.transaction():
            chart = await self._repository.get_chart_info(chart_id)
            if chart is None:
                raise ValueError("The selected rate chart was not found")
            config = await self._repository.get_formula_config(chart_id)

        ctx.total = 2
        await ctx.report()

        path = ctx.job_dir / _RESULT_FILE
        writer = await asyncio.to_thread(XlsxSheetWriter, path, FORMULA_SHEET, tmpdir=ctx.job_dir)
        try:
            rows = self._build_rows(config)
            await asyncio.to_thread(writer.write_rows, rows)
            ctx.processed = len(rows)
            await ctx.checkpoint()
            await asyncio.to_thread(writer.write_instructions)
        except BaseException:
            await asyncio.to_thread(_close_quietly, writer, path)
            raise

        await asyncio.to_thread(writer.close)
        return ProcessorResult(result_file=_RESULT_FILE)

    def _build_rows(self, config) -> list[list]:
        cow_fat = config.cow_standard_fat if config and config.cow_standard_fat is not None else 4.0
        cow_snf = config.cow_standard_snf if config and config.cow_standard_snf is not None else 8.5
        cow_rate = config.cow_standard_rate if config and config.cow_standard_rate is not None else 35.0
        cow_fat_pct = config.cow_fat_percentage if config and config.cow_fat_percentage is not None else 60.0
        cow_snf_pct = config.cow_snf_percentage if config and config.cow_snf_percentage is not None else 40.0

        buf_fat = config.buffalo_standard_fat if config and config.buffalo_standard_fat is not None else 6.5
        buf_snf = config.buffalo_standard_snf if config and config.buffalo_standard_snf is not None else 9.0
        buf_rate = config.buffalo_standard_rate if config and config.buffalo_standard_rate is not None else 48.0
        buf_fat_pct = config.buffalo_fat_percentage if config and config.buffalo_fat_percentage is not None else 60.0
        buf_snf_pct = config.buffalo_snf_percentage if config and config.buffalo_snf_percentage is not None else 40.0

        row_cow_dict = {
            "animal_type": "COW",
            "standard_fat": cow_fat,
            "standard_snf": cow_snf,
            "standard_rate": cow_rate,
            "fat_percentage": cow_fat_pct,
            "snf_percentage": cow_snf_pct,
        }

        row_buf_dict = {
            "animal_type": "BUFFALO",
            "standard_fat": buf_fat,
            "standard_snf": buf_snf,
            "standard_rate": buf_rate,
            "fat_percentage": buf_fat_pct,
            "snf_percentage": buf_snf_pct,
        }

        return [
            [format_cell(col, row_cow_dict[col.key]) for col in self._columns],
            [format_cell(col, row_buf_dict[col.key]) for col in self._columns],
        ]


def _close_quietly(writer: XlsxSheetWriter, path: Path) -> None:
    try:
        writer.close()
    except Exception:
        pass
    path.unlink(missing_ok=True)
