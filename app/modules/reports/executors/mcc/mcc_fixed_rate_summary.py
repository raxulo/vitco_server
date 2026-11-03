"""
Fixed-rate MCC reports.

Both list every collection entry (date, VLCC, shift) with its CLR, detection
and net quantity:

- MCC Fixed Rate Summary          : a single date + shift.
- MCC Fixed Rate Payment Summary  : a date/shift range, with a Signature column.

Net quantity is not stored; it is the quantity the amount was paid on,
i.e. amount / rate (falls back to quantity when the rate is 0).
"""

from typing import Any

from sqlalchemy import Integer, cast, select

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.reports.application.dto import ReportMetadata, ReportResult
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.core.numeric import to_fixed_2, truncate_float
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from app.modules.vlcc.infrastructure.models import VlccModel


class MccFixedRateSummaryExecutor(ReportExecutor):
    __slots__ = ("_database",)

    report_name = "MCC Fixed Rate Summary"

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m, v = MccCollectionModel, VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)

        stmt = (
            select(
                m.collected_at,
                m.shift,
                v.vlcc_code,
                m.quantity,
                m.fat_percent,
                m.snf_percent,
                m.clr_value,
                m.detection_value,
                m.rate_per_unit,
                m.total_amount,
                m.quantity_collection_mode,
                m.measurement_mode,
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .where(*self.filters(m, query))
            .order_by(m.collected_at, m.shift, cast(v.vlcc_code, Integer), m.id)
        )

        rows: list[dict[str, Any]] = []
        total_qty = total_net_qty = total_amount = fat_qty = clr_qty = 0.0

        for row in (await session.execute(stmt)).mappings():
            quantity = float(row["quantity"] or 0)
            fat = float(row["fat_percent"] or 0)
            clr = float(row["clr_value"] or 0)
            rate = float(row["rate_per_unit"] or 0)
            amount = float(row["total_amount"] or 0)
            net_qty = amount / rate if rate else quantity

            rows.append(self._row(row, quantity, fat, clr, net_qty, rate, amount))

            total_qty += quantity
            total_net_qty += net_qty
            total_amount += amount
            fat_qty += quantity * fat
            clr_qty += quantity * clr

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            rows=rows,
            footer={
                "average_fat": self.avg_fat(fat_qty, total_qty),
                "average_clr": to_fixed_2(clr_qty / total_qty) if total_qty > 0 else 0.0,
                "average_rate": self.avg_rate(total_amount, total_net_qty),
                "total_amount": to_fixed_2(total_amount),
                "total_quantity": to_fixed_2(total_qty),
            },
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    def _row(self, row, quantity, fat, clr, net_qty, rate, amount) -> dict[str, Any]:
        # Keys follow `headers` order: report templates render rows positionally
        return {
            "date": row["collected_at"].strftime("%d/%m/%y"),
            "vlcc_code": row["vlcc_code"],
            "shift": self._shift_code(row["shift"]),
            "quantity": self.marked(quantity, self.is_manual(row["quantity_collection_mode"])),
            "fat": self.marked(fat, self.is_manual(row["measurement_mode"])),
            "snf": to_fixed_2(float(row["snf_percent"] or 0)),
            "clr": to_fixed_2(clr),
            "detection": truncate_float(row["detection_value"], 3),
            "net_qty": to_fixed_2(net_qty),
            "rate": to_fixed_2(rate),
            "amount": to_fixed_2(amount),
        }

    @staticmethod
    def _shift_code(shift) -> str:
        return "M" if shift == CollectionShift.MORNING else "E"

    @property
    def headers(self) -> list[str]:
        return [
            "Date",
            "VLCC Code",
            "Shift",
            "Qty",
            "Fat",
            "SNF",
            "CLR",
            "Detection",
            "Net Qty",
            "Rate",
            "Amount",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date=True,
            shift=True,
            milk_type=True,
            mcc_id=True,
            is_deleted=True,
        )

    def build_metadata(self, query: ReportQuery, mcc) -> ReportMetadata:
        return ReportMetadata(
            time=query.formatted_time,
            date=query.formatted_start_date,
            start_shift=query.formatted_start_shift,
            owner_name=mcc.get("owner_name") if mcc else None,
            role="mcc",
            report_name=self.report_name,
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=(mcc.get("city") if mcc else None) or "—",
        )


class MccFixedRatePaymentSummaryExecutor(MccFixedRateSummaryExecutor):
    __slots__ = ()

    report_name = "MCC Fixed Rate Payment Summary"

    def _row(self, row, quantity, fat, clr, net_qty, rate, amount) -> dict[str, Any]:
        r = super()._row(row, quantity, fat, clr, net_qty, rate, amount)
        del r["snf"]
        r["signature"] = ""  # left blank for the VLCC to sign on the printout
        return r

    @property
    def headers(self) -> list[str]:
        return [
            "Date",
            "VLCC Code",
            "Shift",
            "Qty",
            "FAT",
            "CLR",
            "Detection",
            "Net Qty",
            "Rate",
            "Amount",
            "Signature",
        ]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date_range=True,
            shift_range=True,
            milk_type=True,
            mcc_id=True,
            is_deleted=True,
        )

    def build_metadata(self, query: ReportQuery, mcc) -> ReportMetadata:
        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            owner_name=mcc.get("owner_name") if mcc else None,
            role="mcc",
            report_name=self.report_name,
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=(mcc.get("city") if mcc else None) or "—",
        )
