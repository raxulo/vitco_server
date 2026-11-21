import asyncio
from app.core.numeric import fixed
from app.modules.reports.executors.base import ReportExecutor
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.collections.mcc_collection.domain.enums import QuantityCollectionMode
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.reports.application.queries import ReportQuery
from sqlalchemy import select
from sqlalchemy import func
from app.modules.reports.application.dto import ReportResult
from app.modules.reports.application.dto import ReportMetadata
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class MccWeightShiftSummaryExecutor(ReportExecutor):

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

        rows_stmt = (
            select(
                m.collected_at.label("time"),
                v.vlcc_code.label("vlcc_code"),
                v.route_code.label("route_code"),
                m.sample_number.label("sample"),
                m.can_count.label("can"),
                m.quantity.label("quantity"),
                m.quantity_collection_mode.label("quantity_collection_mode"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(*filters)
            .order_by(m.collected_at,v.vlcc_code, m.id)
            .offset(query.offset)
            .limit(query.size)
        )

        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.can_count), 0).label("can"),
                func.count(m.id).label("total_samples"),
            )
            .select_from(m)
            .where(*filters)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        rows = []
        for row in rows_result.mappings():
            r = dict(row)
            if r.get("time") and hasattr(r["time"], "strftime"):
                r["time"] = r["time"].strftime("%H:%M")
            # '*' marks a manually collected quantity; mode is not a display column
            manual = "*" if r.pop("quantity_collection_mode") == QuantityCollectionMode.MANUAL else ""
            r["quantity"] = f"{fixed(r['quantity'])}{manual}"
            rows.append(r)

        totals = totals_result.mappings().one()

        quantity = totals["quantity"]
        total_samples = totals["total_samples"]

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "total_samples": total_samples,
                "total_quantity": quantity,
                "total_cans": totals["can"],
            },
            rows=rows,
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "Time",
            "V.Code",
            "R.Code",
            "Sample",
            "Can",
            "Qty.",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date=True,
            shift=True,
            mcc_id=True,
            is_deleted=True,
        )

    def build_metadata(self, query: ReportQuery, mcc):
        address = (mcc.get("city") or mcc["city"] if mcc else None) or "—"
        return ReportMetadata(
            time=query.formatted_time,
            date=query.formatted_start_date,
            start_shift=query.formatted_start_shift,
            role="mcc",
            report_name="Weight Shift Summary",
            owner_name=mcc.get("owner_name", None) if mcc else None,
            name=mcc["name"] if mcc else "—",
            code=mcc["code"] if mcc else "—",
            address=address,
        )
