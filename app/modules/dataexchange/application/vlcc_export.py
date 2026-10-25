"""
VLCC Export Processor

Writes every non-deleted VLCC of one owner to an xlsx file in VLCC_SHEET format.
The next keyset page is fetched from the database while the previous page is being
written to the file in a worker thread.

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
from app.modules.dataexchange.domain.sheets import VLCC_SHEET
from app.modules.dataexchange.infrastructure.vlcc_repository import VlccExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter

_RESULT_FILE = "result.xlsx"


class VlccExportProcessor:

    __slots__ = ("_database", "_repository", "_page_size", "_columns")

    kind = ExcelJobKind.VLCC_EXPORT

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: VlccExchangeRepository,
        page_size: int = 1000,
    ) -> None:
        self._database = database
        self._repository = repository
        self._page_size = page_size
        self._columns = VLCC_SHEET.export_columns()

    async def run(self, ctx: JobContext) -> ProcessorResult:
        owner_id = ctx.job.target_id
        if owner_id is None:
            raise ValueError("No owner selected for this VLCC export")

        async with self._database.transaction():
            ctx.total = await self._repository.count_export(owner_id)
        await ctx.report()

        path = ctx.job_dir / _RESULT_FILE
        writer = await asyncio.to_thread(XlsxSheetWriter, path, VLCC_SHEET, tmpdir=ctx.job_dir)
        try:
            await self._copy_pages(ctx, owner_id, writer)
            await asyncio.to_thread(writer.write_instructions)
        except BaseException:
            await asyncio.to_thread(_close_quietly, writer, path)
            raise
        await asyncio.to_thread(writer.close)
        return ProcessorResult(result_file=_RESULT_FILE)

    async def _copy_pages(self, ctx: JobContext, owner_id: UUID, writer: XlsxSheetWriter) -> None:
        after: tuple[str, UUID] | None = None
        writing: asyncio.Future | None = None
        try:
            while True:
                async with self._database.transaction():
                    page = await self._repository.export_page(owner_id, after, self._page_size)
                if writing is not None:
                    await writing
                    writing = None
                if not page:
                    return
                rows = [self._format(row) for row in page]
                writing = asyncio.ensure_future(asyncio.to_thread(writer.write_rows, rows))
                last_row = page[-1]
                after = (last_row.vlcc_code, last_row.vlcc_id)
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
