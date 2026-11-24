from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select

from app.core.numeric import fixed
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import QuantityCollectionMode
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.reports.application.dto import (
    LedgerResult,
    ReportMetadata,
    ReportResult,
)
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from app.modules.vlcc.infrastructure.models import VlccModel


class MccWeightRouteWiseExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m, v = MccCollectionModel, VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)
        filters = self.filters(m, query)

        route = self.code_as_int(v.route_code)

        # =========================================================
        # Rows
        # =========================================================
        rows_stmt = (
            select(
                route.label("route_code"),
                m.collected_at.label("date_time"),
                v.vlcc_code.label("vlcc_code"),
                m.sample_number.label("sample"),
                m.can_count.label("can"),
                m.quantity.label("quantity"),
                m.quantity_collection_mode.label("quantity_collection_mode"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(
                *filters,
                *self.code_between(v.route_code, query.route_from, query.route_to),
            )
            .order_by(
                route,
                m.collected_at,
                v.vlcc_code,
            )
        )

        # =========================================================
        # Totals
        # =========================================================
        totals_stmt = (
            select(
                route.label("route_code"),
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.can_count), 0).label("can"),
                func.count(m.id).label("total_samples"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(
                *filters,
                *self.code_between(v.route_code, query.route_from, query.route_to),
            )
            .group_by(route)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        # =========================================================
        # Group rows by route
        # =========================================================
        grouped: dict[int, list[dict]] = defaultdict(list)

        for row in rows_result.mappings():
            # '*' marks a manually collected quantity
            manual = "*" if row["quantity_collection_mode"] == QuantityCollectionMode.MANUAL else ""
            grouped[row["route_code"]].append(
                {
                    "date": row["date_time"].strftime("%d/%m"),
                    "time": row["date_time"].strftime("%H:%M"),
                    "vlcc_code": row["vlcc_code"],
                    "sample": row["sample"],
                    "can": row["can"],
                    "quantity": f"{fixed(row['quantity'])}{manual}",
                }
            )

        totals = {
            row["route_code"]: row
            for row in totals_result.mappings()
        }

        # =========================================================
        # Build ledgers
        # =========================================================
        ledgers = [
            LedgerResult(
                head={"Route Code": route_code},
                rows=grouped[route_code],
                footer={
                    "total_samples": totals[route_code]["total_samples"],
                    "total_cans": totals[route_code]["can"],
                    "total_quantity": totals[route_code]["quantity"],
                },
            )
            # One ledger per route, ascending by route code
            for route_code in sorted(grouped)
        ]

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            ledger=ledgers,
            total=len(ledgers),
            footer={},
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "Date",
            "Time",
            "V.Code",
            "Sample",
            "Can",
            "Qty",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date_range=True,
            shift_range=True,
            mcc_id=True,
            is_deleted=True,
        )

    @staticmethod
    def build_metadata(
        query: ReportQuery,
        mcc: dict | None,
    ) -> ReportMetadata:
        address = (mcc.get("city") if mcc else None) or None

        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            start_route=query.route_from,
            end_route=query.route_to,
            role="mcc",
            report_name="MCC Weight Route Wise",
            owner_name=mcc.get("owner_name", None) if mcc else None,
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=address,
        )