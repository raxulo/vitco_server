from datetime import datetime, time, timedelta
from sqlalchemy import select, func, and_
from app.modules.reports.executors.base import ReportExecutor
from app.modules.collections.vlcc_collection.infrastructure.models import DispatchModel
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.application.dto import ReportResult, ReportMetadata
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class DispatchSummaryExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(
        self,
        query: ReportQuery,
    ) -> ReportResult:

        session = self._database.session
        m = DispatchModel

        vlcc = await self.get_vlcc(session, query.vlcc_id)

        # Build date range filters manually
        conditions = []
        if query.vlcc_id:
            conditions.append(m.vlcc_id == query.vlcc_id)

        if query.start_date:
            start = datetime.combine(query.start_date, time.min)
            end_date = query.end_date if query.end_date else query.start_date
            end = datetime.combine(end_date + timedelta(days=1), time.min)
            conditions.append(and_(m.collected_at >= start, m.collected_at < end))

        rows_stmt = (
            select(
                m.collected_at,
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.quantity,
                m.can_count,
            )
            .select_from(m)
            .where(*conditions)
            .order_by(m.collected_at.asc())
        )

        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.can_count), 0).label("can_count"),
                func.coalesce(func.sum(m.fat_percent * m.quantity), 0).label("fat_qty"),
                func.coalesce(func.sum(m.snf_percent * m.quantity), 0).label("snf_qty"),
            )
            .select_from(m)
            .where(*conditions)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        rows = []
        for row in rows_result.mappings():
            r = dict(row)
            dt = r.get("collected_at")
            data = {
                "date": dt.strftime("%d/%m") if dt else "—",
                "time": dt.strftime("%H:%M") if dt else "—",
                "fat": f"{r['fat']}%",
                "snf": f"{r['snf']}%",
                "quantity": r["quantity"],
                "can_count": r["can_count"],
                "shift": "M" if dt.hour < 12 else "E",
            }
            rows.append(data)

        totals = totals_result.mappings().one()
        quantity = totals["quantity"]
        fat_qty = totals["fat_qty"]
        snf_qty = totals["snf_qty"]

        return ReportResult(
            metadata=self.build_metadata(query, vlcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "average_fat": self.avg_fat(fat_qty, quantity),
                "average_snf": self.avg_snf(snf_qty, quantity),
                "total_quantity": quantity,
                "total_cans": totals["can_count"],
            },
            rows=rows,
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "Date",
            "Time",
            "FAT",
            "SNF",
            "Qty.",
            "Can",
            "Shift",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.VLCC,
            date=True,
            date_range=True,
            vlcc_id=True,
        )

    def build_metadata(self, query: ReportQuery, vlcc):
        address = (vlcc.get("city") if vlcc else None) or "—"
        return ReportMetadata(
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            role="vlcc",
            report_name="Dispatch Summary",
            name=vlcc.get("name", "—") if vlcc else "—",
            code=vlcc.get("vlcc_code", "—") if vlcc else "—",
            uic_code=vlcc.get("uic_code", "—") if vlcc else None,
            owner_name=vlcc.get("owner_name", None) if vlcc else None,
            address=address,
        )
