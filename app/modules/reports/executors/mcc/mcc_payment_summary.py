"""
MCC Payment Summary report.

One row per VLCC for the selected period: milk supplied to the MCC, its bank
details, society commission and the net amount payable.

    Soc.Value  = Amount x (soc_percentage / 100)
    Net Amount = Amount + Soc.Value

R/D (round difference), Ded.ADV and Ded.FG are fixed at 0.00 for now.
Quantity / Fat carry a '*' when any of the VLCC's collections in the period
had a manually entered quantity / manually measured fat.
"""

from typing import Any

from sqlalchemy import Integer, case, cast, func, select

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import (
    MeasurementMode,
    QuantityCollectionMode,
)
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.reports.application.dto import ReportMetadata, ReportResult
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from app.modules.vlcc.infrastructure.models import VlccModel

# Placeholders until rounding and deductions are implemented
_ROUND_DIFF = 0.0
_DED_ADVANCE = 0.0
_DED_FG = 0.0


class MccPaymentSummaryExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        session = self._database.session
        m, v, b = MccCollectionModel, VlccModel, BankAccountModel

        mcc = await self.get_mcc(session, query.mcc_id)

        stmt = (
            select(
                v.vlcc_code,
                v.uic_code,
                v.name,
                v.soc_percentage,
                b.account_number,
                b.ifsc_code,
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.quantity * m.fat_percent), 0).label("fat_qty"),
                func.coalesce(func.sum(m.quantity * m.snf_percent), 0).label("snf_qty"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                func.max(
                    case((m.quantity_collection_mode == QuantityCollectionMode.MANUAL, 1), else_=0)
                ).label("manual_quantity"),
                func.max(
                    case((m.measurement_mode == MeasurementMode.MANUAL, 1), else_=0)
                ).label("manual_fat"),
            )
            .select_from(m)
            .join(v, v.id == m.vlcc_id)
            .outerjoin(b, b.id == v.bank_account_id)
            .where(*self.filters(m, query))
            .group_by(
                v.id,
                v.vlcc_code,
                v.uic_code,
                v.name,
                v.soc_percentage,
                b.account_number,
                b.ifsc_code,
            )
            .order_by(cast(v.vlcc_code, Integer).asc())
        )

        rows: list[dict[str, Any]] = []
        totals = dict(quantity=0.0, fat_qty=0.0, snf_qty=0.0, amount=0.0, soc_value=0.0, net_amount=0.0)

        for row in (await session.execute(stmt)).mappings():
            quantity = float(row["quantity"])
            fat_qty = float(row["fat_qty"])
            snf_qty = float(row["snf_qty"])
            amount = float(row["amount"])
            soc_value = round(amount * float(row["soc_percentage"] or 0) / 100, 2)
            net_amount = round(amount + soc_value, 2)

            # Keys follow `headers` order: generic templates render rows positionally
            rows.append(
                {
                    "vlcc_code": row["vlcc_code"],
                    "uic_code": row["uic_code"] or "—",
                    "vlcc_name": row["name"],
                    "account_number": row["account_number"] or "—",
                    "ifsc_code": row["ifsc_code"] or "—",
                    "quantity": f"{quantity:.2f}{'*' if row['manual_quantity'] else ''}",
                    "fat": f"{self.avg_fat(fat_qty, quantity):.2f}{'*' if row['manual_fat'] else ''}",
                    "snf": self.avg_snf(snf_qty, quantity),
                    "rate": self.avg_rate(amount, quantity),
                    "amount": round(amount, 2),
                    "round_diff": _ROUND_DIFF,
                    "soc_value": soc_value,
                    "ded_advance": _DED_ADVANCE,
                    "ded_fg": _DED_FG,
                    "net_amount": net_amount,
                }
            )

            totals["quantity"] += quantity
            totals["fat_qty"] += fat_qty
            totals["snf_qty"] += snf_qty
            totals["amount"] += amount
            totals["soc_value"] += soc_value
            totals["net_amount"] += net_amount

        quantity = totals["quantity"]
        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            rows=rows,
            footer={
                "total_vlcc": len(rows),
                "total_quantity": round(quantity, 2),
                "average_fat": self.avg_fat(totals["fat_qty"], quantity),
                "average_snf": self.avg_snf(totals["snf_qty"], quantity),
                "average_rate": self.avg_rate(totals["amount"], quantity),
                "total_amount": round(totals["amount"], 2),
                "total_round_diff": _ROUND_DIFF,
                "total_soc_value": round(totals["soc_value"], 2),
                "total_ded_advance": _DED_ADVANCE,
                "total_ded_fg": _DED_FG,
                "total_net_amount": round(totals["net_amount"], 2),
            },
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "VLCC Code",
            "UIC Code",
            "VLCC Name",
            "AC No",
            "IFSC Code",
            "Quantity",
            "Fat",
            "SNF",
            "Rate",
            "Amount",
            "R/D",
            "Soc.Value",
            "Ded.ADV",
            "Ded.FG",
            "Net Amount",
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

    @staticmethod
    def build_metadata(query: ReportQuery, mcc) -> ReportMetadata:
        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            owner_name=mcc.get("owner_name") if mcc else None,
            role="mcc",
            report_name="MCC Payment Summary",
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=(mcc.get("city") if mcc else None) or "—",
        )
