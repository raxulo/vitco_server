from app.modules.collections.mcc_collection.domain.enums import MilkType
from app.modules.reports.application.dto import LedgerResult
from collections import defaultdict
from datetime import datetime
import asyncio
from sqlalchemy import Integer, cast, select, func
from app.modules.reports.executors.base import ReportExecutor
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.administration.infrastructure.models import UserModel
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.application.dto import ReportResult, ReportMetadata
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class VlccShiftSummaryExecutor(ReportExecutor):

    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(
        self,
        query: ReportQuery,
    ) -> ReportResult:

        session = self._database.session
        m = VlccCollectionModel
        f = FarmerModel
        u = UserModel

        vlcc = await self.get_vlcc(session, query.vlcc_id)

        filters = self.filters(m, query)

        rows_stmt = (
            select(
                m.collected_at.label("time"),
                f.farmer_code.label("farmer_code"),
                m.quantity,
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.rate_per_unit.label("rate"),
                m.total_amount.label("amount"),
                m.measurement_mode.label("measurement_mode"),
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .join(u, u.id == f.user_id)
            .where(*filters)
            .order_by(cast(f.farmer_code, Integer).asc(), m.collected_at.asc(), m.id.asc())
            .offset(query.offset)
            .limit(query.size)
        )

        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.coalesce(func.sum(m.fat_percent), 0).label("fat"),
                func.coalesce(func.sum(m.snf_percent), 0).label("snf"),
            )
            .select_from(m)
            .where(*filters)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        rows = []
        for row in rows_result.mappings():
            r = dict(row)
            dt = r.get("time")
            if dt is not None:
                if isinstance(dt, datetime):
                    r["time"] = dt.strftime("%H:%M")
            rows.append(r)

        totals = totals_result.mappings().one()

        quantity = totals["quantity"]
        amount = totals["amount"]

        return ReportResult(
            metadata=self.build_metadata(query, vlcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={
                "average_fat": self.avg_fat(totals["fat"], quantity),
                "average_snf": self.avg_snf(totals["snf"], quantity),
                "average_rate": self.avg_rate(amount, quantity),
                "total_quantity": quantity,
                "total_amount": amount,
                "total_samples": len(rows),
            },
            rows=rows,
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m = VlccCollectionModel
        f = FarmerModel
        u = UserModel

        vlcc = await self.get_vlcc(session, query.vlcc_id)
        filters = self.filters(m, query)

        # code_from = int(query.code_from)
        # code_to = int(query.code_to)

        # =========================================================
        # Rows
        # =========================================================
        rows_stmt = (
            select(
                m.collected_at.label("date_time"),
                f.farmer_code.label("farmer_code"),
                m.quantity,
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.milk_type.label("milk_type"),
                m.rate_per_unit.label("rate"),
                m.total_amount.label("amount"),
                m.measurement_mode.label("measurement_mode"),
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .join(u, u.id == f.user_id)
            .where(*filters)
            .order_by(cast(f.farmer_code, Integer).asc(), m.collected_at.asc(), m.id.asc())
            .offset(query.offset)
            .limit(query.size)
        )

        # =========================================================
        # Totals
        # =========================================================
        totals_stmt = (
            select(
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                m.milk_type.label("milk_type"),
                func.coalesce(func.sum(m.fat_percent), 0).label("fat"),
                func.coalesce(func.sum(m.snf_percent), 0).label("snf"),
            )
            .select_from(m)
            .where(*filters)
            .group_by(m.milk_type)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        # =========================================================
        # Group rows by Farmer
        # =========================================================
        grouped: dict[int, list[dict]] = defaultdict(list)
        milk_types: dict[int, str] = {}

        for row in rows_result.mappings():
            milk_type_val = row["milk_type"]
            milk_types[milk_type_val] = milk_type_val
            grouped[milk_type_val].append(
                {
                    "time": f"{row["date_time"].strftime("%H:%M")}{'*' if row["measurement_mode"]==0 else'' }",
                    "code": row["farmer_code"],
                    "quantity": row["quantity"],
                    "fat": row["fat"],
                    "snf": row["snf"],
                    "rate": row["rate"],
                    "amount": row["amount"],
                }
            )

        totals = {
            row["milk_type"]: row
            for row in totals_result.mappings()
        }

        grand_quantity = 0
        grand_amount = 0
        grand_fat = 0
        grand_snf = 0

        for milk_type in totals:
            grand_quantity += totals[milk_type]["quantity"]
            grand_amount += totals[milk_type]["amount"]
            grand_fat += totals[milk_type]["fat"]
            grand_snf += totals[milk_type]["snf"]

        grand_fat = self.avg_fat(grand_fat, grand_quantity)
        grand_snf = self.avg_snf(grand_snf, grand_quantity)
        grand_rate = self.avg_rate(grand_amount, grand_quantity)
        

        # =========================================================
        # Build ledgers
        # =========================================================
        ledgers = [
            LedgerResult(
                head={
                    "Animal Type": MilkType(milk_type_val).name,
                },
                rows=grouped[milk_type_val],
                footer={
                    "average_fat": self.avg_fat(totals[milk_type_val]["fat"], totals[milk_type_val]["quantity"]),
                    "average_snf": self.avg_snf(totals[milk_type_val]["snf"], totals[milk_type_val]["quantity"]),
                    "average_rate": self.avg_rate(totals[milk_type_val]["amount"], totals[milk_type_val]["quantity"]),
                    "total_quantity": totals[milk_type_val]["quantity"],
                    "total_amount": totals[milk_type_val]["amount"],
                },
            )
            for milk_type_val in milk_types
        ]

        return ReportResult(
            metadata=self.build_metadata(query, vlcc),
            report_type=query.report_type.value,
            header=self.headers,
            ledger=ledgers,
            total=len(ledgers),
            footer={
                    "grand_fat": grand_fat,
                    "grand_snf": grand_snf,
                    "grand_rate": grand_rate,
                    "grand_quantity": grand_quantity,
                    "grand_amount": grand_amount,
                },
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "Time",
            "Code",
            "Qty",
            "FAT",
            "SNF",
            "Rate",
            "Amount",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.VLCC,
            date=True,
            shift=True,
            vlcc_id=True,
        )

    def build_metadata(self, query: ReportQuery, vlcc):
        address = (vlcc.get("city") if vlcc else None) or "—"
        return ReportMetadata(
            time=query.formatted_time,
            date=query.formatted_start_date,
            start_shift=query.formatted_start_shift,
            role="vlcc",
            report_name="Provisional Shift Summary",
            owner_name=vlcc.get("owner_name") if vlcc else None,
            uic_code=vlcc.get("uic_code") if vlcc else None,
            name=vlcc.get("name", "—") if vlcc else "—",
            code=vlcc.get("vlcc_code", "—") if vlcc else "—",
            address=address,
        )
