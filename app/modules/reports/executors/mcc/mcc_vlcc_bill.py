from collections import defaultdict
from datetime import datetime

from sqlalchemy import Integer, cast, func, select

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
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


class MccVlccBillExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m, v = MccCollectionModel, VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)
        filters = self.filters(m, query)

        code_from = int(query.code_from)
        code_to = int(query.code_to)

        vlcc_code_int = cast(v.vlcc_code, Integer)

        # =========================================================
        # Rows
        # =========================================================
        rows_stmt = (
            select(
                vlcc_code_int.label("vlcc_code_int"),
                v.vlcc_code.label("vlcc_code"),
                v.name.label("vlcc_name"),
                UserModel.mobile.label("vlcc_mobile"),
                m.collected_at.label("date_time"),
                m.shift.label("shift"),
                m.milk_type.label("milk_type"),
                m.quantity.label("quantity"),
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.rate_per_unit.label("rate"),
                m.total_amount.label("amount"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .outerjoin(UserModel, UserModel.id == v.user_id)
            .where(
                *filters,
                vlcc_code_int.between(code_from, code_to),
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
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.coalesce(func.sum(m.quantity * m.fat_percent), 0).label("fat"),
                func.coalesce(func.sum(m.quantity * m.snf_percent), 0).label("snf"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(
                *filters,
                vlcc_code_int.between(code_from, code_to),
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

        milk_types_map = {0: "Cow", 1: "Buffalo", 2: "Mixed"}
        shift_map = {0: "M", 1: "E"}

        for row in rows_result.mappings():
            code_val = row["vlcc_code_int"]
            vlcc_names[code_val] = row["vlcc_name"]
            vlcc_str_codes[code_val] = row["vlcc_code"]
            vlcc_mobiles[code_val] = row["vlcc_mobile"]

            # Map milk type
            mt = row["milk_type"]
            if hasattr(mt, "value"):
                mt_str = milk_types_map.get(mt.value, mt.name)
            elif isinstance(mt, int):
                mt_str = milk_types_map.get(mt, str(mt))
            else:
                mt_str = str(mt) if mt is not None else "—"

            # Map shift
            sh = row["shift"]
            if hasattr(sh, "value"):
                sh_str = shift_map.get(sh.value, sh.name)
            elif isinstance(sh, int):
                sh_str = shift_map.get(sh, str(sh))
            else:
                sh_str = str(sh) if sh is not None else "—"

            qty = float(row["quantity"] or 0)
            fat = float(row["fat"] or 0)
            snf = float(row["snf"] or 0)
            fat_kg = round(qty * fat / 100, 3)
            snf_kg = round(qty * snf / 100, 3)

            grouped[code_val].append(
                {
                    "date": row["date_time"].strftime("%d/%m"),
                    "shift": sh_str,
                    "milk_type": mt_str,
                    "quantity": row["quantity"],
                    "fat": row["fat"],
                    "snf": row["snf"],
                    "fat_kg": fat_kg,
                    "snf_kg": snf_kg,
                    "rate": row["rate"],
                    "amount": row["amount"],
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
                    "Name": vlcc_names[code_val],
                    "Mobile No": vlcc_mobiles[code_val] or "—",
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
            "Shift",
            "M.Type",
            "Qty",
            "Fat",
            "Snf",
            "FatKG",
            "SnfKG",
            "Rate",
            "Amt.",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date_range=True,
            shift_range=True,
            mcc_id=True,
        )

    @staticmethod
    def build_metadata(
        query: ReportQuery,
        mcc: dict | None,
    ) -> ReportMetadata:
        address = (mcc.get("city") if mcc else None) or "—"

        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            start_code=query.code_from,
            end_code=query.code_to,
            owner_name=mcc.get("owner_name", None) if mcc else None,
            role="mcc",
            report_name="Member Ledger",
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=address,
        )
