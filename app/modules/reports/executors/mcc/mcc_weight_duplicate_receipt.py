"""
MCC Weight Duplicate Receipt report (weight MCCs only).

Re-prints the weight slips one VLCC (the MCC's member, picked by VLCC code)
gave the MCC on the selected date and shift: time, shift, sample, cans and
quantity, with '*' on a manually entered quantity.
"""

from sqlalchemy import select

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
)
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.reports.application.dto import LedgerResult, ReportMetadata, ReportResult
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.modules.reports.executors.mcc.mcc_duplicate_receipt import MccDuplicateReceiptExecutor
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class MccWeightDuplicateReceiptExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        # member_code of an MCC report is the VLCC code
        if not query.member_code:
            raise ValueError("Please enter the VLCC code to print its duplicate receipt.")

        session = self._database.session
        m = MccCollectionModel

        mcc = await self.get_mcc(session, query.mcc_id)
        vlcc = await MccDuplicateReceiptExecutor._find_vlcc(session, query)

        rows = []
        cans = 0
        quantity = 0.0
        if vlcc is not None:
            stmt = (
                select(
                    m.collected_at,
                    m.shift,
                    m.sample_number,
                    m.can_count,
                    m.quantity,
                    m.quantity_collection_mode,
                )
                .where(*self.filters(m, query), m.vlcc_id == vlcc["id"])
                .order_by(m.collected_at, m.id)
            )
            for row in (await session.execute(stmt)).mappings():
                qty = float(row["quantity"] or 0)
                # '*' marks a manually collected quantity
                manual = "*" if row["quantity_collection_mode"] == QuantityCollectionMode.MANUAL else ""
                rows.append({
                    "time": row["collected_at"].strftime("%H:%M"),
                    "shift": "M" if row["shift"] == CollectionShift.MORNING else "E",
                    "sample": row["sample_number"],
                    "can": int(row["can_count"] or 0),
                    "quantity": f"{qty:.2f}{manual}",
                })
                cans += int(row["can_count"] or 0)
                quantity += qty

        return ReportResult(
            metadata=self.build_metadata(query, mcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={},
            ledger=[
                LedgerResult(
                    head={
                        "Code": query.member_code,
                        "Name": vlcc["name"] if vlcc else "VLCC not found",
                        "Mobile No.": (vlcc["mobile"] if vlcc else None) or "—",
                    },
                    rows=rows,
                    footer={
                        "total_samples": len(rows),
                        "total_cans": cans,
                        "total_quantity": round(quantity, 2),
                    } if rows else None,
                )
            ],
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return ["Time", "Shift", "Sample", "Can", "Qty."]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date=True,
            shift=True,
            member_code=True,
            mcc_id=True,
            is_deleted=True,
        )

    @staticmethod
    def build_metadata(query: ReportQuery, mcc: dict | None) -> ReportMetadata:
        return ReportMetadata(
            time=query.formatted_time,
            date=query.formatted_start_date,
            start_shift=query.formatted_start_shift,
            start_code=query.member_code,
            owner_name=mcc.get("owner_name") if mcc else None,
            role="mcc",
            report_name="Weight Duplicate Receipt",
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=(mcc.get("city") if mcc else None) or "—",
        )
