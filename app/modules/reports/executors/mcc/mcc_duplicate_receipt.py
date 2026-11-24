"""
MCC Duplicate Receipt report.

Re-prints every collection one VLCC (the MCC's member, picked by VLCC code)
supplied to the MCC on the selected date and shift.
"""

from sqlalchemy import select

from app.core.numeric import truncate_float
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.reports.application.dto import LedgerResult, ReportMetadata, ReportResult
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.executors.base import ReportExecutor
from app.modules.reports.infrastructure.filters import AppliedOnFilters
from app.modules.vlcc.infrastructure.models import VlccModel


class MccDuplicateReceiptExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        # member_code of an MCC report is the VLCC code
        if not query.member_code:
            raise ValueError("Please enter the VLCC code to print its duplicate receipt.")

        session = self._database.session
        m, v = MccCollectionModel, VlccModel

        mcc = await self.get_mcc(session, query.mcc_id)
        vlcc = await self._find_vlcc(session, query)

        rows = []
        quantity = amount = fat_qty = snf_qty = 0.0
        if vlcc is not None:
            stmt = (
                select(
                    m.collected_at,
                    m.shift,
                    m.quantity,
                    m.fat_percent,
                    m.snf_percent,
                    m.rate_per_unit,
                    m.total_amount,
                    m.quantity_collection_mode,
                    m.measurement_mode,
                )
                .where(*self.filters(m, query), m.vlcc_id == vlcc["id"])
                # One VLCC only (filtered above), so its collections in time order
                .order_by(m.collected_at, m.id)
            )
            for row in (await session.execute(stmt)).mappings():
                qty = float(row["quantity"] or 0)
                rows.append({
                    "date": self.short_date(row["collected_at"]),
                    "shift": "M" if row["shift"] == CollectionShift.MORNING else "E",
                    "quantity": self.marked(qty, self.is_manual(row["quantity_collection_mode"])),
                    "fat": self.marked(row["fat_percent"], self.is_manual(row["measurement_mode"])),
                    "snf": float(row["snf_percent"] or 0),
                    "rate": float(row["rate_per_unit"] or 0),
                    "amount": float(row["total_amount"] or 0),
                })
                quantity += qty
                amount += float(row["total_amount"] or 0)
                fat_qty += qty * float(row["fat_percent"] or 0)
                snf_qty += qty * float(row["snf_percent"] or 0)

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
                        "average_fat": self.avg_fat(fat_qty, quantity),
                        "average_snf": self.avg_snf(snf_qty, quantity),
                        "average_rate": self.avg_rate(amount, quantity),
                        "total_quantity": truncate_float(quantity, 2),
                        "total_amount": truncate_float(amount, 2),
                    } if rows else None,
                )
            ],
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @staticmethod
    async def _find_vlcc(session, query: ReportQuery):
        """The VLCC with this code among those that supply the MCC (created by its user or its creator)."""
        mcc_creators = select(MccModel.user_id).where(MccModel.id == query.mcc_id).union(
            select(MccModel.created_by).where(MccModel.id == query.mcc_id)
        )
        stmt = (
            select(VlccModel.id, VlccModel.name, UserModel.mobile)
            .outerjoin(UserModel, UserModel.id == VlccModel.user_id)
            .where(
                ReportExecutor.code_match(VlccModel.vlcc_code, query.member_code),
                VlccModel.created_by.in_(mcc_creators),
                VlccModel.is_deleted.is_(False),
            )
            .limit(1)
        )
        return (await session.execute(stmt)).mappings().one_or_none()

    @property
    def headers(self) -> list[str]:
        return ["Date", "Shift", "Qty.", "FAT", "SNF", "Rate", "Amount"]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date=True,
            shift=True,
            vlcc_id=True,
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
            report_name="Duplicate Receipt",
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            address=(mcc.get("city") if mcc else None) or None,
        )
