"""
Collection Export Processors (REQ-48, REQ-49, REQ-53, REQ-54, DECISION-028, DECISION-030)

Write the MCC or VLCC collections matching a list page's filters to an xlsx file.
The worker reads them as the requesting user through the list's own access scope,
oldest first in keyset pages. Deleted entries are included and painted red; the
totals leave them out. The next page is fetched while the previous one is written
in a worker thread, and a Summary sheet repeats the filters and totals.

The filters travel in the job's `params.json` (`CollectionExportFilters.to_params`).

Python 3.13+
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.domain.irepository import IMccCollectionRepository
from app.modules.collections.mcc_collection.domain.listing import (
    CollectionPeriod,
    CollectionTotals,
    MccCollectionFilters,
    VlccCollectionFilters,
)
from app.modules.collections.vlcc_collection.domain.irepository import IVlccCollectionRepository
from app.modules.dataexchange.application.column_layout_handler import layout_for_export
from app.modules.dataexchange.application.processor import JobContext, ProcessorResult
from app.modules.dataexchange.domain.column_layout import ColumnLayout
from app.modules.dataexchange.domain.columns import ColumnSpec, SheetSpec
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.irepository import IColumnLayoutRepository
from app.modules.dataexchange.domain.sheets import (
    MCC_COLLECTION_SHEET,
    VLCC_COLLECTION_SHEET,
    CollectionSheet,
)
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.modules.ratechart.domain.enums import MilkType

_RESULT_FILE = "result.xlsx"


# =========================================================
# FILTERS (API -> params.json -> worker)
# =========================================================

@dataclass(slots=True, frozen=True, kw_only=True)
class CollectionExportFilters:
    """A collection list's filters. `mcc_id` only applies to MCC collections."""

    search: str | None = None
    mcc_id: UUID | None = None
    vlcc_id: UUID | None = None
    milk_type: MilkType | None = None
    date_from: date | None = None
    date_to: date | None = None
    start_shift: CollectionShift | None = None
    end_shift: CollectionShift | None = None

    @property
    def period(self) -> CollectionPeriod:
        return CollectionPeriod(
            start_day=self.date_from, end_day=self.date_to,
            start_shift=self.start_shift, end_shift=self.end_shift,
        ).in_order()

    def mcc_filters(self) -> MccCollectionFilters:
        return MccCollectionFilters(
            vlcc_search=self.search, mcc_id=self.mcc_id, vlcc_id=self.vlcc_id,
            milk_type=self.milk_type, period=self.period,
        )

    def vlcc_filters(self) -> VlccCollectionFilters:
        return VlccCollectionFilters(
            farmer_search=self.search, vlcc_id=self.vlcc_id, milk_type=self.milk_type, period=self.period,
        )

    def to_params(self) -> dict[str, Any]:
        """JSON-safe form for the job's params.json."""
        return {
            "search": self.search,
            "mcc_id": str(self.mcc_id) if self.mcc_id else None,
            "vlcc_id": str(self.vlcc_id) if self.vlcc_id else None,
            "milk_type": None if self.milk_type is None else int(self.milk_type),
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "start_shift": None if self.start_shift is None else int(self.start_shift),
            "end_shift": None if self.end_shift is None else int(self.end_shift),
        }

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> CollectionExportFilters:
        def optional(key: str, convert):
            value = params.get(key)
            return None if value is None or value == "" else convert(value)

        return cls(
            search=optional("search", str),
            mcc_id=optional("mcc_id", UUID),
            vlcc_id=optional("vlcc_id", UUID),
            milk_type=optional("milk_type", lambda value: MilkType(int(value))),
            date_from=optional("date_from", date.fromisoformat),
            date_to=optional("date_to", date.fromisoformat),
            start_shift=optional("start_shift", lambda value: CollectionShift(int(value))),
            end_shift=optional("end_shift", lambda value: CollectionShift(int(value))),
        )


# =========================================================
# PROCESSORS
# =========================================================

class _CollectionExportProcessor:
    """
    Shared run loop; subclasses name the kind, sheet, repository and filters.

    The columns follow the layout of the user the export belongs to (REQ-55, REQ-56),
    resolved per job: two jobs may run at once with different layouts.
    """

    __slots__ = ("_database", "_repository", "_storage", "_layouts", "_page_size")

    kind: ExcelJobKind
    sheet: SheetSpec
    layout_sheet: CollectionSheet
    title: str
    search_label: str

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: IMccCollectionRepository | IVlccCollectionRepository,
        storage: ExchangeStorage,
        layouts: IColumnLayoutRepository | None = None,
        page_size: int = 1000,
    ) -> None:
        self._database = database
        self._repository = repository
        self._storage = storage
        self._layouts = layouts
        self._page_size = page_size

    def _filters(self, filters: CollectionExportFilters):
        raise NotImplementedError

    def _party_labels(self, filters: CollectionExportFilters, first_row: dict[str, Any] | None) -> list[tuple[str, str]]:
        raise NotImplementedError

    # ---------------------------------------------------------

    async def run(self, ctx: JobContext) -> ProcessorResult:
        params = await asyncio.to_thread(self._storage.read_params, ctx.job_dir)
        chosen = CollectionExportFilters.from_params(params)
        filters = self._filters(chosen)

        async with self._database.transaction():
            ctx.total = await self._repository.count_export(ctx.owner, filters)
            totals = await self._repository.totals(ctx.owner, filters)
            layout = (
                await layout_for_export(self._layouts, ctx.owner)
                if self._layouts is not None else ColumnLayout.default()
            )
        await ctx.report()

        columns = layout.columns_for(self.layout_sheet)
        path = ctx.job_dir / _RESULT_FILE
        writer = await asyncio.to_thread(XlsxSheetWriter, path, self.sheet, columns=columns, tmpdir=ctx.job_dir)
        try:
            first_row = await self._copy_pages(ctx, filters, writer, columns)
            summary = self._summary(chosen, first_row, totals)
            await asyncio.to_thread(writer.write_summary, self.title, summary)
        except BaseException:
            await asyncio.to_thread(_close_quietly, writer, path)
            raise
        await asyncio.to_thread(writer.close)
        return ProcessorResult(result_file=_RESULT_FILE)

    async def _copy_pages(
        self,
        ctx: JobContext,
        filters,
        writer: XlsxSheetWriter,
        columns: tuple[ColumnSpec, ...],
    ) -> dict[str, Any] | None:
        after: tuple[datetime, UUID] | None = None
        first_row: dict[str, Any] | None = None
        writing: asyncio.Future | None = None
        try:
            while True:
                async with self._database.transaction():          # short read transaction per page
                    page = await self._repository.export_page(ctx.owner, filters, after, self._page_size)
                if writing is not None:
                    await writing                                 # previous page finished while we queried
                    writing = None
                if not page:
                    return first_row
                if first_row is None:
                    first_row = page[0]
                rows = [_format(row, columns) for row in page]
                deleted = [bool(row.get("is_deleted")) for row in page]
                writing = asyncio.ensure_future(asyncio.to_thread(writer.write_rows, rows, deleted))
                after = (page[-1]["collected_at"], page[-1]["id"])
                ctx.processed += len(page)
                await ctx.checkpoint()
        finally:
            if writing is not None and not writing.done():
                await asyncio.gather(writing, return_exceptions=True)

    def _summary(
        self,
        chosen: CollectionExportFilters,
        first_row: dict[str, Any] | None,
        totals: CollectionTotals,
    ) -> list[tuple[str, Any]]:
        period = chosen.period
        rows: list[tuple[str, Any]] = [
            ("From", _period_end(period.start_day, period.start_shift)),
            ("To", _period_end(period.end_day, period.end_shift)),
            *self._party_labels(chosen, first_row),
            ("Milk Type", _label(chosen.milk_type) if chosen.milk_type is not None else "All"),
            (self.search_label, chosen.search or "—"),
            ("", ""),
            ("Entries", totals.entries),
            ("Total Quantity", float(totals.total_quantity)),
            ("Total Amount", float(totals.total_amount)),
            ("Average FAT %", float(totals.avg_fat)),
            ("Average SNF %", float(totals.avg_snf)),
            ("Deleted Entries", totals.deleted_entries),
            ("", ""),
            ("Note", "Red rows are deleted entries. They are not in the totals above."),
        ]
        return rows


class MccCollectionExportProcessor(_CollectionExportProcessor):

    __slots__ = ()

    kind = ExcelJobKind.MCC_COLLECTION_EXPORT
    sheet = MCC_COLLECTION_SHEET
    layout_sheet = CollectionSheet.MCC
    title = "MCC Collections"
    search_label = "VLCC Search"

    def _filters(self, filters: CollectionExportFilters) -> MccCollectionFilters:
        return filters.mcc_filters()

    def _party_labels(self, filters: CollectionExportFilters, first_row: dict[str, Any] | None) -> list[tuple[str, str]]:
        return [
            ("MCC", _chosen(filters.mcc_id, first_row, "mcc_code", "mcc_name")),
            ("VLCC", _chosen(filters.vlcc_id, first_row, "vlcc_code", "vlcc_name")),
        ]


class VlccCollectionExportProcessor(_CollectionExportProcessor):

    __slots__ = ()

    kind = ExcelJobKind.VLCC_COLLECTION_EXPORT
    sheet = VLCC_COLLECTION_SHEET
    layout_sheet = CollectionSheet.VLCC
    title = "VLCC Collections"
    search_label = "Farmer Search"

    def _filters(self, filters: CollectionExportFilters) -> VlccCollectionFilters:
        return filters.vlcc_filters()

    def _party_labels(self, filters: CollectionExportFilters, first_row: dict[str, Any] | None) -> list[tuple[str, str]]:
        return [("VLCC", _chosen(filters.vlcc_id, first_row, "vlcc_code", "vlcc_name"))]


# =========================================================
# HELPERS
# =========================================================

def _format(row: dict[str, Any], columns: tuple[ColumnSpec, ...]) -> list[Any]:
    """One entry as the cells of `columns`, in their order."""
    collected_at: datetime | None = row.get("collected_at")
    rank = row.get("rank")
    values = {
        **row,
        "date": collected_at.date() if collected_at else None,
        "time": collected_at.strftime("%I:%M %p") if collected_at else None,
        "chart_rank": f"R{rank}" if rank is not None else None,
        "deleted": "Yes" if row.get("is_deleted") else None,
    }
    return [_cell(values.get(column.key)) for column in columns]


def _label(value: Enum) -> str:
    return value.name.replace("_", " ").title()


def _cell(value: Any) -> Any:
    if isinstance(value, Enum):
        return _label(value)
    if isinstance(value, Decimal):
        return float(value)
    return value


def _chosen(selected: UUID | None, first_row: dict[str, Any] | None, code_key: str, name_key: str) -> str:
    """'All', or the selected centre as 'code - name' (read from the exported rows, which all belong to it)."""
    if selected is None:
        return "All"
    if first_row is None or not first_row.get(name_key):
        return "Selected (no entries)"
    code = first_row.get(code_key)
    return f"{code} - {first_row[name_key]}" if code else str(first_row[name_key])


def _period_end(day: date | None, shift: CollectionShift | None) -> str:
    if day is None and shift is None:
        return "—"
    parts = [day.strftime("%d-%m-%Y")] if day else []
    if shift is not None:
        parts.append(_label(shift))
    return " ".join(parts)


def _close_quietly(writer: XlsxSheetWriter, path: Path) -> None:
    try:
        writer.close()
    except Exception:
        pass
    path.unlink(missing_ok=True)


__all__ = [
    "CollectionExportFilters",
    "MccCollectionExportProcessor",
    "VlccCollectionExportProcessor",
]
