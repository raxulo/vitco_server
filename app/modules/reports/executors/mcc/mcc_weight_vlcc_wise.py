from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select

from app.core.numeric import fixed
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
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


class MccWeightVlccWiseExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m, v = MccCollectionModel, VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)
        filters = self.filters(m, query)

        vlcc_code_int = self.code_as_int(v.vlcc_code)

        # =========================================================
        # Rows
        # =========================================================
        rows_stmt = (
            select(
                vlcc_code_int.label("vlcc_code_int"),
                v.vlcc_code.label("vlcc_code"),
                v.name.label("vlcc_name"),
                UserModel.mobile.label("vlcc_mobile"),
                v.route_code.label("route_code"),
                m.collected_at.label("date_time"),
                m.sample_number.label("sample"),
                m.can_count.label("can"),
                m.quantity.label("quantity"),
                m.quantity_collection_mode.label("quantity_collection_mode"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .outerjoin(UserModel, UserModel.id == v.user_id)
            .where(
                *filters,
                *self.code_between(v.vlcc_code, query.code_from, query.code_to),
            )
            .order_by(
                vlcc_code_int,
                m.collected_at,
            )
        )

        # =========================================================
        # Totals
        # =========================================================
        totals_stmt = (
            select(
                vlcc_code_int.label("vlcc_code_int"),
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.can_count), 0).label("can"),
                func.count(m.id).label("total_samples"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(
                *filters,
                *self.code_between(v.vlcc_code, query.code_from, query.code_to),
            )
            .group_by(vlcc_code_int)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        # =========================================================
        # Group rows by VLCC code
        # =========================================================
        grouped: dict[int, list[dict]] = defaultdict(list)
        vlcc_names: dict[int, str] = {}
        vlcc_str_codes: dict[int, str] = {}
        vlcc_mobiles: dict[int, str | None] = {}

        for row in rows_result.mappings():
            code_val = row["vlcc_code_int"]
            vlcc_names[code_val] = row["vlcc_name"]
            vlcc_str_codes[code_val] = row["vlcc_code"]
            vlcc_mobiles[code_val] = row["vlcc_mobile"]
            # '*' marks a manually collected quantity
            manual = "*" if row["quantity_collection_mode"] == QuantityCollectionMode.MANUAL else ""
            grouped[code_val].append(
                {
                    "date": row["date_time"].strftime("%d/%m"),
                    "time": row["date_time"].strftime("%H:%M"),
                    "route":row["route_code"],
                    "sample": row["sample"],
                    "can": row["can"],
                    "quantity": f"{fixed(row['quantity'])}{manual}",
                }
            )

        totals = {
            row["vlcc_code_int"]: row
            for row in totals_result.mappings()
        }

        # =========================================================
        # Build ledgers
        # =========================================================
        ledgers = [
            LedgerResult(
                head={
                    "Code": vlcc_str_codes[code_val],
                    "VLCC Name": vlcc_names[code_val],
                    "Mobile No": vlcc_mobiles[code_val] or "—",
                },
                rows=grouped[code_val],
                footer={
                    "total_samples": totals[code_val]["total_samples"],
                    "total_cans": totals[code_val]["can"],
                    "total_quantity": totals[code_val]["quantity"],
                },
            )
            # One ledger per VLCC, ascending by numeric VLCC code
            for code_val in sorted(grouped)
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
            "Route",
            "Sample",
            "Can",
            "Quantity",
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
            start_code=query.code_from,
            end_code=query.code_to,
            role="mcc",
            report_name="MCC Weight VLCC Wise",
            owner_name=mcc.get("owner_name", None) if mcc else None,
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=address,
        )
