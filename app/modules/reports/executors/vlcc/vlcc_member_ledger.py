from collections import defaultdict
from datetime import datetime

from sqlalchemy import Integer, cast, func, select

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.collections.vlcc_collection.infrastructure.models import (
    VlccCollectionModel,
)
from app.modules.reports.application.dto import (
    LedgerResult,
    ReportMetadata,
    ReportResult,
)
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class VlccMemberLedgerExecutor(ReportExecutor):
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
        # Rows
        # =========================================================
        rows_stmt = (
            select(
                farmer_code_int.label("farmer_code_int"),
                f.farmer_code.label("farmer_code"),
                u.name.label("farmer_name"),
                m.collected_at.label("date_time"),
                m.quantity.label("quantity"),
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.rate_per_unit.label("rate"),
                m.total_amount.label("amount"),
                m.quantity_collection_mode,
                m.measurement_mode,
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .join(u, u.id == f.user_id)
            .where(
                *filters,
                farmer_code_int.between(code_from, code_to),
            )
            .order_by(
                farmer_code_int,
                m.collected_at,
            )
        )

        # =========================================================
        # Totals
        # =========================================================
        totals_stmt = (
            select(
                farmer_code_int.label("farmer_code_int"),
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.coalesce(func.sum(m.quantity * m.fat_percent), 0).label("fat"),
                func.coalesce(func.sum(m.quantity * m.snf_percent), 0).label("snf"),
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .where(
                *filters,
                farmer_code_int.between(code_from, code_to),
            )
            .group_by(farmer_code_int)
        )

        rows_result = await session.execute(rows_stmt)
        totals_result = await session.execute(totals_stmt)

        # =========================================================
        # Group rows by Farmer
        # =========================================================
        grouped: dict[int, list[dict]] = defaultdict(list)
        farmer_names: dict[int, str] = {}
        farmer_str_codes: dict[int, str] = {}

        for row in rows_result.mappings():
            code_val = row["farmer_code_int"]
            farmer_names[code_val] = row["farmer_name"]
            farmer_str_codes[code_val] = row["farmer_code"]
            grouped[code_val].append(
                {
                    "date": row["date_time"].strftime("%d/%m"),
                    "time": row["date_time"].strftime("%H:%M"),
                    "quantity": self.marked(row["quantity"], self.is_manual(row["quantity_collection_mode"])),
                    "fat": self.marked(row["fat"], self.is_manual(row["measurement_mode"])),
                    "snf": row["snf"],
                    "rate": row["rate"],
                    "amount": row["amount"],
                }
            )

        totals = {
            row["farmer_code_int"]: row
            for row in totals_result.mappings()
        }

        # =========================================================
        # Build ledgers
        # =========================================================
        ledgers = [
            LedgerResult(
                head={
                    "Code": farmer_str_codes[code_val],
                    "Name": farmer_names[code_val],
                },
                rows=grouped[code_val],
                footer={
                    "average_fat": self.avg_fat(totals[code_val]["fat"], totals[code_val]["quantity"]),
                    "average_snf": self.avg_snf(totals[code_val]["snf"], totals[code_val]["quantity"]),
                    "average_rate": self.avg_rate(totals[code_val]["amount"], totals[code_val]["quantity"]),
                    "total_quantity": totals[code_val]["quantity"],
                    "total_amount": totals[code_val]["amount"],
                },
            )
            for code_val in range(code_from, code_to + 1)
            if code_val in grouped
        ]

        return ReportResult(
            metadata=self.build_metadata(query, vlcc),
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
            "Qty.",
            "FAT",
            "SNF",
            "Rate",
            "Amount",
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
            report_name="Provisional Milk Bill",
            name=vlcc.get("name", "—") if vlcc else "—",
            code=vlcc.get("vlcc_code", "—") if vlcc else "—",
            uic_code=vlcc.get("uic_code") if vlcc else None,
            address=address,
        )
