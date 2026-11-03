import asyncio
from app.core.numeric import fixed
from app.modules.reports.executors.base import ReportExecutor
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.collections.mcc_collection.domain.enums import (
    MeasurementMode,
    QuantityCollectionMode,
)
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.reports.application.queries import ReportQuery
from sqlalchemy import select
from sqlalchemy import func
from app.modules.reports.application.dto import ReportResult
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

        rows_stmt = (
            select(
                v.vlcc_code.label("vlcc_code"),
                # v.uic_code.label("uic_code"),
                v.name.label("vlcc_name"),
                # m.milk_type.label("type"),
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.quantity,
                m.rate_per_unit.label("rate"),
                m.total_amount.label("amount"),
                m.measurement_mode.label("measurement_mode"),
                m.quantity_collection_mode.label("quantity_collection_mode"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(*filters)
            .order_by(v.vlcc_code, m.collected_at, m.id)
            .offset(query.offset)
            .limit(query.size)
        )

        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.coalesce(
                    func.sum(m.quantity * m.fat_percent),
                    0,
                ).label("fat"),
                func.coalesce(
                    func.sum(m.quantity * m.snf_percent),
                    0,
                ).label("snf"),
            )
            .select_from(m)
            .where(*filters)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        milk_types_map = {0: "Cow", 1: "Buffalo", 2: "Mixed"}
        rows = []
        for row in rows_result.mappings():
            r = dict(row)
            t = r.get("type")
            if t is not None:
                if isinstance(t, int):
                    r["type"] = milk_types_map.get(t, str(t))
                elif hasattr(t, "value"):
                    r["type"] = milk_types_map.get(t.value, t.name)
                elif hasattr(t, "name"):
                    r["type"] = t.name
            # '*' marks manual entries; mode fields are not display columns
            qty_manual = "*" if r.pop("quantity_collection_mode") == QuantityCollectionMode.MANUAL else ""
            fat_manual = "*" if r.pop("measurement_mode") == MeasurementMode.MANUAL else ""
            r["quantity"] = f"{fixed(r['quantity'])}{qty_manual}"
            r["fat"] = f"{fixed(r['fat'])}{fat_manual}"
            rows.append(r)

        totals = totals_result.mappings().one()

        quantity = totals["quantity"]
        amount = totals["amount"]

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "average_fat": self.avg_fat(
                    totals["fat"],
                    quantity,
                ),
                "average_snf": self.avg_snf(
                    totals["snf"],
                    quantity,
                ),
                "average_rate": self.avg_rate(
                    amount,
                    quantity,
                ),
                "total_quantity": quantity,
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
            "V.C.",
            "Name",
            "FAT",
            "SNF",
            "Qty",
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
        address = (mcc.get("city") or mcc["city"] if mcc else None) or "—"
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