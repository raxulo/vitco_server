from app.core.numeric import fixed
from app.modules.reports.application.dto import LedgerResult
from app.modules.reports.executors.base import ReportExecutor
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.reports.application.queries import ReportQuery
from sqlalchemy import select, func
from app.modules.reports.application.dto import ReportResult
from app.modules.reports.application.dto import ReportMetadata
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class MccWeightDateWiseExecutor(ReportExecutor):

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

        # Apply custom code range filters on VLCC code
        filters += self.code_between(v.vlcc_code, query.code_from, query.code_to)

        # One row per VLCC: every date in the range added up, plus how many days it had collections
        day = func.date(m.collected_at)
        rows_stmt = (
            select(
                v.vlcc_code.label("vlcc_code"),
                func.count(func.distinct(day)).label("days"),
                v.name.label("vlcc_name"),
                func.sum(m.can_count).label("can"),
                func.sum(m.quantity).label("quantity"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(*filters)
            .group_by(v.vlcc_code, v.name)
            .order_by(self.code_as_int(v.vlcc_code).asc())
            .offset(query.offset)
            .limit(query.size)
        )

        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.can_count), 0).label("can"),
                func.count(func.distinct(m.collected_at)).label("total_days"),
                func.count(func.distinct(m.vlcc_id)).label("total_vlcc"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(*filters)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        rows = []
        for row in rows_result.mappings():
            # Keys follow `headers` order: report templates render rows positionally.
            # The quantity is a total, so it never carries the manual '*'.
            rows.append({
                "vlcc_code": row["vlcc_code"],
                "days": int(row["days"] or 0),
                "vlcc_name": row["vlcc_name"],
                "can": int(row["can"] or 0),
                "quantity": fixed(row["quantity"]),
            })

        totals = totals_result.mappings().one()

        quantity = totals["quantity"]

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "total_vlcc": totals["total_vlcc"],
                "total_cans": totals["can"],
                "total_quantity": quantity,
            },
            ledger=[LedgerResult(
                rows=rows,
                head={
                    "Code: " : f"{query.code_from or 0} to {query.code_to or 0}",
                }
            )],
            total=1,
            page=query.page,
            size=query.size,
            
        )

    @property
    def headers(self) -> list[str]:
        return [
            "V.Code",
            "Days",
            "Name",
            "Can",
            "Quantity",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            shift_range=True,
            date_range=True,
            code_range=True,
            mcc_id=True,
            milk_type=False,
            is_deleted=True,
        )

    def build_metadata(self, query: ReportQuery, mcc):
        address = (mcc.get("city") if mcc else None) or None
        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            start_code=query.code_from,
            end_code=query.code_to,
            role="mcc",
            report_name="MCC Weight Date Wise",
            owner_name=mcc.get("owner_name", None) if mcc else None,
            name=mcc["name"] if mcc else "—",
            code=mcc["code"] if mcc else "—",
            address=address,
        )
