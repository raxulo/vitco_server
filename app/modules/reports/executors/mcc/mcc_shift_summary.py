from collections import defaultdict

from app.core.numeric import fixed
from app.modules.reports.executors.base import ReportExecutor
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.collections.mcc_collection.domain.enums import (
    MeasurementMode,
    MilkType,
    QuantityCollectionMode,
)
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.reports.application.queries import ReportQuery
from sqlalchemy import select
from sqlalchemy import func
from app.modules.reports.application.dto import LedgerResult, ReportResult
from app.modules.reports.application.dto import ReportMetadata
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class MccShiftSummaryExecutor(ReportExecutor):

    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(
        self,
        query: ReportQuery,
    ) -> ReportResult:

        session = self._database.session
        m = MccCollectionModel
        v = VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)

        filters = self.filters(m, query)

        # Active rows feed the milk-type ledgers and the grand totals; deleted
        # rows are shown only in their own "DELETED" ledger.
        active_filters = [*filters, m.is_deleted.is_(False)]
        deleted_filters = [*filters, m.is_deleted.is_(True)]

        def rows_stmt(conditions: list):
            return (
                select(
                    m.sample_number.label("sample_number"),
                    v.vlcc_code.label("vlcc_code"),
                    v.name.label("vlcc_name"),
                    m.quantity,
                    m.fat_percent.label("fat"),
                    m.snf_percent.label("snf"),
                    m.rate_per_unit.label("rate"),
                    m.total_amount.label("amount"),
                    m.milk_type.label("milk_type"),
                    m.measurement_mode.label("measurement_mode"),
                    m.quantity_collection_mode.label("quantity_collection_mode"),
                )
                .select_from(m)
                .join(v, v.id == m.vlcc_id)
                .where(*conditions)
                .order_by(m.collected_at, m.id)
                .offset(query.offset)
                .limit(query.size)
            )

        def totals_columns():
            return (
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.coalesce(func.sum(m.quantity * m.fat_percent), 0).label("fat"),
                func.coalesce(func.sum(m.quantity * m.snf_percent), 0).label("snf"),
                func.count(m.id).label("samples"),
            )

        totals_stmt = (
            select(m.milk_type.label("milk_type"), *totals_columns())
            .select_from(m)
            .where(*active_filters)
            .group_by(m.milk_type)
        )
        deleted_totals_stmt = (
            select(*totals_columns())
            .select_from(m)
            .where(*deleted_filters)
        )

        rows_result = await session.execute(rows_stmt(active_filters))
        totals_result = await session.execute(totals_stmt)
        deleted_rows_result = await session.execute(rows_stmt(deleted_filters))
        deleted_totals = (await session.execute(deleted_totals_stmt)).mappings().one()

        # Group active rows by milk type
        grouped: dict[int, list[dict]] = defaultdict(list)
        for row in rows_result.mappings():
            grouped[row["milk_type"]].append(self._report_row(row))

        deleted_rows = [self._report_row(row) for row in deleted_rows_result.mappings()]

        totals = {row["milk_type"]: row for row in totals_result.mappings()}

        # One ledger per milk type, in enum order (COW, BUFFALO, MIXED)
        ledgers = [
            LedgerResult(
                head={"Animal Type": MilkType(milk_type).name},
                rows=grouped[milk_type],
                footer=self._footer(totals[milk_type]),
            )
            for milk_type in sorted(grouped)
        ]

        # Deleted rows: own totals, never added to the grand totals.
        if deleted_rows:
            ledgers.append(
                LedgerResult(
                    head={"Animal Type": "DELETED"},
                    rows=deleted_rows,
                    footer=self._footer(deleted_totals),
                )
            )

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer=self._grand_footer(totals.values()),
            ledger=ledgers,
            # Sample, V.C., Name, Qty, FAT, SNF, Rate, Amount
            column_widths=[8, 8, 30, 12, 8, 8, 11, 15],
            # VLCC name is for the web report only; the API (mobile app) leaves it out
            web_only_columns={"vlcc_name": "Name"},
            total=len(ledgers),
            page=query.page,
            size=query.size,
        )

    def _footer(self, totals) -> dict:
        quantity = totals["quantity"]
        amount = totals["amount"]
        return {
            "average_fat": self.avg_fat(totals["fat"], quantity),
            "average_snf": self.avg_snf(totals["snf"], quantity),
            "average_rate": self.avg_rate(amount, quantity),
            "total_quantity": quantity,
            "total_amount": amount,
            "total_samples": totals["samples"],
        }

    def _grand_footer(self, milk_type_totals) -> dict:
        quantity = amount = fat = snf = samples = 0
        for t in milk_type_totals:
            quantity += t["quantity"]
            amount += t["amount"]
            fat += t["fat"]
            snf += t["snf"]
            samples += t["samples"]
        return {
            "grand_fat": self.avg_fat(fat, quantity),
            "grand_snf": self.avg_snf(snf, quantity),
            "grand_rate": self.avg_rate(amount, quantity),
            "grand_quantity": quantity,
            "grand_amount": amount,
            "grand_samples": samples,
        }

    @staticmethod
    def _report_row(row) -> dict:
        r = dict(row)
        # '*' marks manual entries; mode and milk-type fields are not display columns
        r.pop("milk_type")
        qty_manual = "*" if r.pop("quantity_collection_mode") == QuantityCollectionMode.MANUAL else ""
        fat_manual = "*" if r.pop("measurement_mode") == MeasurementMode.MANUAL else ""
        r["quantity"] = f"{fixed(r['quantity'])}{qty_manual}"
        r["fat"] = f"{fixed(r['fat'])}{fat_manual}"
        return r

    @property
    def headers(self) -> list[str]:
        return [
            "S.No",
            "V.C.",
            "Name",
            "Qty",
            "FAT",
            "SNF",
            "Rate",
            "Amount",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date=True,
            shift=True,
            mcc_id=True,
        )

    def build_metadata(self, query: ReportQuery, mcc):
        address = (mcc.get("city") if mcc else None) or None
        return ReportMetadata(
            time=query.formatted_time,
            date=query.formatted_start_date,
            start_shift=query.formatted_start_shift,
            owner_name=mcc.get("owner_name", None) if mcc else None,
            role="mcc",
            report_name="MCC Shift Summary",
            name=mcc["name"] if mcc else "—",
            code=mcc["code"] if mcc else "—",
            address=address,
        )
