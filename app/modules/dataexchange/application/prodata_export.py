"""
Prodata Rate-Chart Export Processor

Writes all rows of one Prodata rate chart to an xlsx file in row order (REQ-17).
Paging is keyset-based on row_number, writing rows in worker threads.

Python 3.13+
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.database.manager import DatabaseManager
from app.modules.dataexchange.application.processor import JobContext, ProcessorResult
from app.modules.dataexchange.domain.columns import format_cell
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.sheets import PRODATA_SHEET
from app.modules.dataexchange.infrastructure.prodata_repository import ProdataExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter

_RESULT_FILE = "result.xlsx"


class ProdataExportProcessor:

    __slots__ = ("_database", "_repository", "_page_size", "_columns")

    kind = ExcelJobKind.PRODATA_EXPORT

    def __init__(self, *, database: DatabaseManager, repository: ProdataExchangeRepository, page_size: int = 1000) -> None:
        self._database = database
        self._repository = repository
        self._page_size = page_size
        self._columns = PRODATA_SHEET.export_columns()

    async def run(self, ctx: JobContext) -> ProcessorResult:
        chart_id = ctx.job.target_id
        if chart_id is None:
            raise ValueError("No rate chart selected for this export")

        async with self._database.transaction():
            ctx.total = await self._repository.count_export(chart_id)
        await ctx.report()

        path = ctx.job_dir / _RESULT_FILE
        writer = await asyncio.to_thread(XlsxSheetWriter, path, PRODATA_SHEET, tmpdir=ctx.job_dir)
        try:
            await self._copy_pages(ctx, chart_id, writer)
            await asyncio.to_thread(writer.write_instructions)
        except BaseException:
            await asyncio.to_thread(_close_quietly, writer, path)
            raise
        await asyncio.to_thread(writer.close)
        return ProcessorResult(result_file=_RESULT_FILE)

    async def _copy_pages(self, ctx: JobContext, chart_id, writer: XlsxSheetWriter) -> None:
        after: int | None = None
        writing: asyncio.Future | None = None
        try:
            while True:
                async with self._database.transaction():
                    page = await self._repository.export_page(chart_id, after, self._page_size)
                if writing is not None:
                    await writing
                    writing = None
                if not page:
                    return
                rows = [self._format(row) for row in page]
                writing = asyncio.ensure_future(asyncio.to_thread(writer.write_rows, rows))
                after = page[-1].row_number
                ctx.processed += len(page)
                await ctx.checkpoint()
        finally:
            if writing is not None and not writing.done():
                await asyncio.gather(writing, return_exceptions=True)

    def _format(self, row) -> list:
        mapping = row._mapping
        return [format_cell(column, mapping[column.key]) for column in self._columns]


def _close_quietly(writer: XlsxSheetWriter, path: Path) -> None:
    try:
        writer.close()
    except Exception:
        pass
    path.unlink(missing_ok=True)
