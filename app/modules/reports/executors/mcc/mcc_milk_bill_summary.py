"""
MCC Milk Bill Summary report.

One row per VLCC that supplied the MCC within the date / shift range:
total quantity, average rate and total amount, plus a signature column.
"""

from sqlalchemy import Integer, cast, func, select

from app.core.numeric import truncate_float
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.reports.application.dto import ReportMetadata, ReportResult
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from app.modules.vlcc.infrastructure.models import VlccModel


class MccMilkBillSummaryExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m, v = MccCollectionModel, VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)
        filters = self.filters(m, query)

        rows_stmt = (
            select(
                v.vlcc_code.label("code"),
                v.name.label("name"),
                func.sum(m.quantity).label("total_quantity"),
                func.sum(m.total_amount).label("total_amount"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(*filters)
            .group_by(v.id, v.vlcc_code, v.name)
            # One row per VLCC: sort by VLCC code only. Ordering by an ungrouped
            # column (collected_at) is rejected by PostgreSQL (GroupingError).
            .order_by(cast(v.vlcc_code, Integer).asc())
            .offset(query.offset)
            .limit(query.size)
        )

        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.count(func.distinct(m.vlcc_id)).label("total_vlcc"),
            )
            .select_from(m)
            .where(*filters)
        )

        rows = []
        for row in (await session.execute(rows_stmt)).mappings():
            qty = float(row["total_quantity"] or 0)
            amount = float(row["total_amount"] or 0)
            # Keys follow `headers` order: report templates render rows positionally
            rows.append({
                "code": row["code"],
                "name": row["name"],
                "total_quantity": truncate_float(qty, 2),
                "average_rate": self.avg_rate(amount, qty),
                "total_amount": truncate_float(amount, 2),
                "sign": "─────",
            })

        totals = (await session.execute(totals_stmt)).mappings().one()
        quantity = float(totals["quantity"])
        amount = float(totals["amount"])

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "total_vlcc": totals["total_vlcc"],
                "total_quantity": truncate_float(quantity, 2),
                "average_rate": self.avg_rate(amount, quantity),
                "total_amount": truncate_float(amount, 2),
            },
            rows=rows,
            total=totals["total_vlcc"],
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return ["Code", "Name", "T.Qty", "Avg.Rate", "T.Amt", "Sign."]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date_range=True,
            shift_range=True,
            mcc_id=True,
            is_deleted=True,
        )

    @staticmethod
    def build_metadata(query: ReportQuery, mcc: dict | None) -> ReportMetadata:
        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            owner_name=mcc.get("owner_name") if mcc else None,
            role="mcc",
            report_name="Milk Bill Summary",
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=(mcc.get("city") if mcc else None) or "—",
        )
