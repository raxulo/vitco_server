from sqlalchemy import Integer, cast, func, select
from app.modules.reports.executors.base import ReportExecutor
from app.modules.administration.infrastructure.models import UserModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.collections.vlcc_collection.infrastructure.models import (
    VlccCollectionModel,
)
from app.modules.reports.application.dto import (
    ReportMetadata,
    ReportResult,
)
from app.modules.reports.application.queries import ReportQuery
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class VlccMilkBillSummaryExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m = VlccCollectionModel
        f = FarmerModel
        u = UserModel

        vlcc = await self.get_vlcc(session, query.vlcc_id)
        filters = self.filters(m, query)

        code_from = int(query.code_from)
        code_to = int(query.code_to)

        farmer_code_int = cast(f.farmer_code, Integer)

        # =========================================================
        # Rows query (Grouped by Farmer)
        # =========================================================
        rows_stmt = (
            select(
                f.farmer_code.label("code"),
                u.name.label("name"),
                func.sum(m.quantity).label("total_quantity"),
                func.sum(m.total_amount).label("total_amount"),
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .join(u, u.id == f.user_id)
            .where(
                *filters,
                farmer_code_int.between(code_from, code_to),
            )
            .group_by(f.farmer_code, u.name)
            .order_by(farmer_code_int.asc())
            .offset(query.offset)
            .limit(query.size)
        )

        # =========================================================
        # Grand Totals
        # =========================================================
        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .where(
                *filters,
                farmer_code_int.between(code_from, code_to),
            )
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        rows = []
        for row in rows_result.mappings():
            r = dict(row)
            qty = float(r["total_quantity"] or 0)
            amount = float(r["total_amount"] or 0)
            avg_rate = self.avg_rate(amount, qty)

            ordered_row = {
                "code": r["code"],
                "name": r["name"],
                "total_quantity": r["total_quantity"],
                "average_rate": avg_rate,
                "total_amount": r["total_amount"],
                "sign": "_____"
            }
            rows.append(ordered_row)

        totals = totals_result.mappings().one()
        quantity = totals["quantity"]
        amount = totals["amount"]

        return ReportResult(
            metadata=self.build_metadata(query, vlcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "total_quantity": quantity,
                "average_rate": self.avg_rate(amount, quantity),
                "total_amount": amount,
            },
            rows=rows,
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "Code",
            "Name",
            "T.Qty",
            "Avg.Rate",
            "T.Amt",
            "Sign."
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.VLCC,
            date_range=True,
            shift_range=True,
            vlcc_id=True,
        )

    @staticmethod
    def build_metadata(
        query: ReportQuery,
        vlcc: dict | None,
    ) -> ReportMetadata:
        address = (vlcc.get("city") if vlcc else None) or "—"

        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            start_code=query.code_from,
            end_code=query.code_to,
            owner_name=vlcc.get("owner_name", None) if vlcc else None,
            role="vlcc",
            report_name="Provisional Milk Bill Summary",
            name=vlcc.get("name", "—") if vlcc else "—",
            code=vlcc.get("vlcc_code", "—") if vlcc else "—",
            uic_code=vlcc.get("uic_code") if vlcc else None,
            address=address,
        )
        
