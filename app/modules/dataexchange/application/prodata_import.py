"""
Prodata Rate-Chart Import Processor

Replaces all rows of one Prodata rate chart from an Excel file in one
atomic transaction (REQ-18, DECISION-005).

Validation is all-or-nothing:
- Any invalid row (fat_min > fat_max, snf_min > snf_max, negative rates,
  or overlapping FAT/SNF ranges) rejects the entire file without modifying
  the database, generating a discarded-rows report.
- On valid import, all existing rows of the chart are deleted and replaced
  in one transaction.

Python 3.13+
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.database.manager import DatabaseManager
from app.modules.dataexchange.application.processor import (
    ExchangeProcessor,
    JobContext,
    ProcessorResult,
)
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import PRODATA_SHEET
from app.modules.dataexchange.infrastructure.prodata_repository import ProdataExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import ExtraColumn, RawRow, XlsxSheetReader, XlsxSheetWriter

_REPORT_FILE = "discarded_rows.xlsx"

_EXTRA_COLUMNS = (
    ExtraColumn("Row No", 10),
    ExtraColumn("Reason", 60),
)


@dataclass(slots=True)
class _ParsedRow:
    row_no: int
    raw: RawRow
    row_number: int | None
    fat_min: float | None
    fat_max: float | None
    snf_min: float | None
    snf_max: float | None
    fat_rate_per_kg: float | None
    snf_rate_per_kg: float | None
    snf_cutoff: float | None
    snf_deduction: float | None
    reason: str | None = None


class ProdataImportProcessor(ExchangeProcessor):

    __slots__ = ("_database", "_repository")

    kind = ExcelJobKind.PRODATA_IMPORT

    def __init__(self, *, database: DatabaseManager, repository: ProdataExchangeRepository) -> None:
        self._database = database
        self._repository = repository

    async def run(self, ctx: JobContext) -> ProcessorResult:
        chart_id = ctx.job.target_id
        if chart_id is None and not ctx.job.dry_run:
            raise ValueError("No rate chart selected for this import")
        if not ctx.job.source_file:
            raise ValueError("Import job has no file")

        source = ctx.job_dir / ctx.job.source_file
        reader = XlsxSheetReader(source, PRODATA_SHEET, scratch_dir=ctx.job_dir)
        await asyncio.to_thread(reader.__enter__)

        parsed_rows: list[_ParsedRow] = []
        try:
            ctx.total = reader.estimated_rows
            await ctx.report()

            # Read all rows into memory (Prodata charts typically have tens to thousands of rows)
            batches = reader.iter_batches(1000)
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
            # Empty file: nothing to replace
            return ProcessorResult()

        # Step 1: Validate individual row constraints
        for row in parsed_rows:
            self._validate_row_bounds(row)

        # Step 2: Validate interval overlaps among rows with valid bounds
        self._validate_overlaps(parsed_rows)

        # Check for any failures
        failed_rows = [r for r in parsed_rows if r.reason is not None]

        if failed_rows:
            # All-or-nothing rejection: write rejected report and save nothing
            await self._write_report(ctx, failed_rows)
            ctx.inserted = 0
            ctx.updated = 0
            ctx.discarded = len(failed_rows)
            return ProcessorResult(report_file=_REPORT_FILE)

        # Step 3: All rows are valid -> atomic replacement
        records = []
        for idx, r in enumerate(parsed_rows, start=1):
            row_num = r.row_number if r.row_number is not None else idx
            records.append(dict(
                id=uuid4(),
                rate_chart_id=chart_id,
                row_number=row_num,
                fat_min=r.fat_min,
                fat_max=r.fat_max,
                snf_min=r.snf_min,
                snf_max=r.snf_max,
                fat_rate_per_kg=r.fat_rate_per_kg,
                snf_rate_per_kg=r.snf_rate_per_kg,
                snf_cutoff=r.snf_cutoff,
                snf_deduction=r.snf_deduction,
            ))

        if not ctx.job.dry_run and chart_id is not None:
            async with self._database.transaction():
                await self._repository.replace_rows(chart_id, records)

        ctx.inserted = len(records)
        ctx.updated = 0
        ctx.discarded = 0
        return ProcessorResult()

    def _parse_row(self, raw: RawRow) -> _ParsedRow:
        c = raw.cells
        return _ParsedRow(
            row_no=raw.row_no,
            raw=raw,
            row_number=c.get("row_number"),
            fat_min=c.get("fat_min"),
            fat_max=c.get("fat_max"),
            snf_min=c.get("snf_min"),
            snf_max=c.get("snf_max"),
            fat_rate_per_kg=c.get("fat_rate_per_kg"),
            snf_rate_per_kg=c.get("snf_rate_per_kg"),
            snf_cutoff=c.get("snf_cutoff"),
            snf_deduction=c.get("snf_deduction"),
        )

    def _validate_row_bounds(self, row: _ParsedRow) -> None:
        if row.reason is not None:
            return

        # Check required fields
        if row.fat_min is None:
            row.reason = "FAT Min is required"
            return
        if row.fat_max is None:
            row.reason = "FAT Max is required"
            return

        # Check FAT range
        if row.fat_min < 0.0 or row.fat_min > 20.0:
            row.reason = f"FAT Min ({row.fat_min}) must be between 0.0 and 20.0"
            return
        if row.fat_max < 0.0 or row.fat_max > 20.0:
            row.reason = f"FAT Max ({row.fat_max}) must be between 0.0 and 20.0"
            return
        if row.fat_min > row.fat_max:
            row.reason = f"FAT Min ({row.fat_min}) exceeds FAT Max ({row.fat_max})"
            return

        # Check SNF range
        if row.snf_min is not None and (row.snf_min < 0.0 or row.snf_min > 20.0):
            row.reason = f"SNF Min ({row.snf_min}) must be between 0.0 and 20.0"
            return
        if row.snf_max is not None and (row.snf_max < 0.0 or row.snf_max > 20.0):
            row.reason = f"SNF Max ({row.snf_max}) must be between 0.0 and 20.0"
            return
        if row.snf_min is not None and row.snf_max is not None and row.snf_min > row.snf_max:
            row.reason = f"SNF Min ({row.snf_min}) exceeds SNF Max ({row.snf_max})"
            return

        # Check rates
        if row.fat_rate_per_kg is not None and row.fat_rate_per_kg < 0.0:
            row.reason = f"FAT Rate ({row.fat_rate_per_kg}) cannot be negative"
            return
        if row.snf_rate_per_kg is not None and row.snf_rate_per_kg < 0.0:
            row.reason = f"SNF Rate ({row.snf_rate_per_kg}) cannot be negative"
            return
        if row.snf_cutoff is not None and row.snf_cutoff < 0.0:
            row.reason = f"SNF Cut-off ({row.snf_cutoff}) cannot be negative"
            return
        if row.snf_deduction is not None and row.snf_deduction < 0.0:
            row.reason = f"SNF Deduction ({row.snf_deduction}) cannot be negative"
            return

    def _validate_overlaps(self, rows: list[_ParsedRow]) -> None:
        valid_rows = [r for r in rows if r.reason is None]
        for i in range(len(valid_rows)):
            row_b = valid_rows[i]
            if row_b.reason is not None:
                continue

            for j in range(i):
                row_a = valid_rows[j]
                if row_a.reason is not None:
                    continue

                if self._check_overlap(row_a, row_b):
                    row_b.reason = (
                        f"Range overlaps with row {row_a.row_no} "
                        f"(FAT {row_a.fat_min}-{row_a.fat_max})"
                    )
                    break

    @staticmethod
    def _check_overlap(a: _ParsedRow, b: _ParsedRow) -> bool:
        """
        Two intervals [A_min, A_max] and [B_min, B_max] overlap if:
        max(A_min, B_min) < min(A_max, B_max) or (A_min == B_min and A_max == B_max).
        Touching at boundary (e.g. 3.0-4.0 and 4.0-5.0) is allowed.
        """
        if a.fat_min is None or a.fat_max is None or b.fat_min is None or b.fat_max is None:
            return False

        fat_overlap = (
            max(a.fat_min, b.fat_min) < min(a.fat_max, b.fat_max)
            or (a.fat_min == b.fat_min and a.fat_max == b.fat_max)
        )
        if not fat_overlap:
            return False

        # If both rows specify an SNF interval, they only overlap if SNF ALSO overlaps
        if (
            a.snf_min is not None
            and a.snf_max is not None
            and b.snf_min is not None
            and b.snf_max is not None
        ):
            snf_overlap = (
                max(a.snf_min, b.snf_min) < min(a.snf_max, b.snf_max)
                or (a.snf_min == b.snf_min and a.snf_max == b.snf_max)
            )
            return snf_overlap

        # If either row lacks SNF boundaries, FAT overlap alone is a conflict
        return True

    async def _write_report(self, ctx: JobContext, failed_rows: list[_ParsedRow]) -> None:
        report_path = ctx.job_dir / _REPORT_FILE
        columns = PRODATA_SHEET.import_columns()
        writer = await asyncio.to_thread(
            XlsxSheetWriter,
            report_path,
            PRODATA_SHEET,
            columns=columns,
            extra_columns=_EXTRA_COLUMNS,
            tmpdir=ctx.job_dir,
        )
        try:
            lines = []
            for r in failed_rows:
                cells = [r.raw.cells.get(col.key) for col in columns]
                lines.append([*cells, r.row_no, r.reason or "Invalid"])
            await asyncio.to_thread(writer.write_rows, lines)
            await asyncio.to_thread(writer.write_instructions)
        finally:
            await asyncio.to_thread(writer.close)
