"""
Formula Rate-Chart Import Processor

Validates and atomically updates the formula configuration of a
rate chart from an Excel workbook (REQ-21).

Validation is all-or-nothing:
- Any invalid row (non-positive standard values, FAT% + SNF% != 100%)
  rejects the entire file without modifying the database, generating
  a discarded-rows report.
- On valid import, the formula configuration is saved in one transaction.

Python 3.13+
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.modules.dataexchange.application.processor import (
    ExchangeProcessor,
    JobContext,
    ProcessorResult,
)
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import FORMULA_SHEET
from app.modules.dataexchange.infrastructure.formula_repository import FormulaExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import ExtraColumn, RawRow, XlsxSheetReader, XlsxSheetWriter

_REPORT_FILE = "discarded_rows.xlsx"

_EXTRA_COLUMNS = (
    ExtraColumn("Row No", 10),
    ExtraColumn("Reason", 60),
)


@dataclass(slots=True)
class _ParsedFormulaRow:
    row_no: int
    raw: RawRow
    animal_type: str | None
    standard_fat: float | None
    standard_snf: float | None
    standard_rate: float | None
    fat_percentage: float | None
    snf_percentage: float | None
    reason: str | None = None


class FormulaImportProcessor(ExchangeProcessor):

    __slots__ = ("_database", "_repository")

    kind = ExcelJobKind.FORMULA_IMPORT

    def __init__(self, *, database: DatabaseManager, repository: FormulaExchangeRepository) -> None:
        self._database = database
        self._repository = repository

    async def run(self, ctx: JobContext) -> ProcessorResult:
        chart_id = ctx.job.target_id
        if chart_id is None and not ctx.job.dry_run:
            raise ValueError("No rate chart selected for this import")
        if not ctx.job.source_file:
            raise ValueError("Import job has no file")

        source = ctx.job_dir / ctx.job.source_file
        reader = XlsxSheetReader(source, FORMULA_SHEET, scratch_dir=ctx.job_dir)
        await asyncio.to_thread(reader.__enter__)

        parsed_rows: list[_ParsedFormulaRow] = []
        try:
            ctx.total = reader.estimated_rows
            await ctx.report()

            batches = reader.iter_batches(100)
            while True:
                batch = await asyncio.to_thread(next, batches, None)
                if batch is None:
                    break
                for raw_row in batch:
                    parsed_rows.append(self._parse_row(raw_row))
                ctx.processed = len(parsed_rows)
                await ctx.checkpoint()
        finally:
            await asyncio.to_thread(reader.close)

        ctx.total = len(parsed_rows)
        ctx.processed = len(parsed_rows)

        if not parsed_rows:
            return ProcessorResult()

        for row in parsed_rows:
            self._validate_row(row)

        failed_rows = [r for r in parsed_rows if r.reason is not None]
        if failed_rows:
            await self._write_report(ctx, failed_rows)
            ctx.inserted = 0
            ctx.updated = 0
            ctx.discarded = len(failed_rows)
            return ProcessorResult(report_file=_REPORT_FILE)

        cow_params: dict[str, float] = {}
        buf_params: dict[str, float] = {}

        for r in parsed_rows:
            animal = (r.animal_type or "").upper()
            target = cow_params if animal == "COW" else buf_params
            if r.standard_fat is not None:
                target["standard_fat"] = r.standard_fat
            if r.standard_snf is not None:
                target["standard_snf"] = r.standard_snf
            if r.standard_rate is not None:
                target["standard_rate"] = r.standard_rate
            if r.fat_percentage is not None:
                target["fat_percentage"] = r.fat_percentage
            if r.snf_percentage is not None:
                target["snf_percentage"] = r.snf_percentage

        if not ctx.job.dry_run and chart_id is not None:
            async with self._database.transaction():
                await self._repository.save_formula_config(
                    chart_id,
                    cow_standard_fat=cow_params.get("standard_fat"),
                    cow_standard_snf=cow_params.get("standard_snf"),
                    cow_standard_rate=cow_params.get("standard_rate"),
                    cow_fat_percentage=cow_params.get("fat_percentage"),
                    cow_snf_percentage=cow_params.get("snf_percentage"),
                    buffalo_standard_fat=buf_params.get("standard_fat"),
                    buffalo_standard_snf=buf_params.get("standard_snf"),
                    buffalo_standard_rate=buf_params.get("standard_rate"),
                    buffalo_fat_percentage=buf_params.get("fat_percentage"),
                    buffalo_snf_percentage=buf_params.get("snf_percentage"),
                )

        ctx.inserted = len(parsed_rows)
        ctx.updated = 0
        ctx.discarded = 0
        return ProcessorResult()

    def _parse_row(self, raw: RawRow) -> _ParsedFormulaRow:
        c = raw.cells
        animal = str(c.get("animal_type") or "").strip().upper()
        return _ParsedFormulaRow(
            row_no=raw.row_no,
            raw=raw,
            animal_type=animal or None,
            standard_fat=c.get("standard_fat"),
            standard_snf=c.get("standard_snf"),
            standard_rate=c.get("standard_rate"),
            fat_percentage=c.get("fat_percentage"),
            snf_percentage=c.get("snf_percentage"),
        )

    def _validate_row(self, row: _ParsedFormulaRow) -> None:
        if not row.animal_type or row.animal_type not in ("COW", "BUFFALO"):
            row.reason = f"Animal type must be COW or BUFFALO, got '{row.animal_type}'"
            return

        if row.standard_fat is None or row.standard_fat <= 0:
            row.reason = "Standard FAT must be greater than 0"
            return

        if row.standard_snf is None or row.standard_snf <= 0:
            row.reason = "Standard SNF must be greater than 0"
            return

        if row.standard_rate is None or row.standard_rate <= 0:
            row.reason = "Standard Rate must be greater than 0"
            return

        fat_pct = row.fat_percentage if row.fat_percentage is not None else 0.0
        snf_pct = row.snf_percentage if row.snf_percentage is not None else 0.0

        if fat_pct < 0 or snf_pct < 0:
            row.reason = "FAT and SNF percentage ratios cannot be negative"
            return

        total_ratio = fat_pct + snf_pct
        if abs(total_ratio - 100.0) > 0.05:
            row.reason = f"FAT ({fat_pct}%) and SNF ({snf_pct}%) contribution must sum to 100% (currently {total_ratio}%)"
            return

    async def _write_report(self, ctx: JobContext, failed_rows: list[_ParsedFormulaRow]) -> None:
        report_path = ctx.job_dir / _REPORT_FILE
        columns = FORMULA_SHEET.import_columns()
        writer = await asyncio.to_thread(
            XlsxSheetWriter,
            report_path,
            FORMULA_SHEET,
            columns=columns,
            extra_columns=_EXTRA_COLUMNS,
            tmpdir=ctx.job_dir,
        )
        try:
            lines = []
            for r in failed_rows:
                cells = [r.raw.cells.get(col.key) for col in columns]
                lines.append([*cells, r.row_no, r.reason or "Invalid formula parameters"])
            await asyncio.to_thread(writer.write_rows, lines)
            await asyncio.to_thread(writer.write_instructions)
        finally:
            await asyncio.to_thread(writer.close)
