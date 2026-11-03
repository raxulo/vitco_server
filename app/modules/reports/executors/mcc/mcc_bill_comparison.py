"""
MCC Milk Bill Comparison report.

For one VLCC, compares what the VLCC dispatched against what the MCC
received, shift by shift. A row exists for every (date, shift) on which
either side has an entry; the missing side is reported as zero.

Dispatches carry no rate, so each dispatch is priced from the MCC's assigned
rate charts: the MCC collection of that shift supplies the chart rank
(missing/null -> 1), and rank N selects the Nth active assignment by priority.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.clock import to_naive_ist
from app.core.numeric import truncate_float
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.collections.mcc_collection.domain.enums import CollectionShift, MilkType
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.collections.vlcc_collection.infrastructure.models import (
    DispatchModel,
)
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.application.handler import RateChartHandler
from app.modules.ratechart.infrastructure.models import (
    RateChartAssignmentModel,
    RateChartModel,
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


class _Bucket:
    """Running quantity-weighted totals for one side of one shift."""

    __slots__ = ("quantity", "fat_qty", "snf_qty", "amount", "manual_quantity", "manual_fat")

    def __init__(self) -> None:
        self.quantity = Decimal("0")
        self.fat_qty = Decimal("0")
        self.snf_qty = Decimal("0")
        self.amount = Decimal("0")
        # Any entry in the bucket with a manual quantity / manually measured FAT ('*')
        self.manual_quantity = False
        self.manual_fat = False

    def add(self, quantity, fat, snf, amount, *, manual_quantity=False, manual_fat=False) -> None:
        q = Decimal(quantity or 0)
        self.quantity += q
        self.fat_qty += q * Decimal(fat or 0)
        self.snf_qty += q * Decimal(snf or 0)
        self.amount += Decimal(amount or 0)
        self.manual_quantity |= manual_quantity
        self.manual_fat |= manual_fat

    def merge(self, other: "_Bucket") -> None:
        self.quantity += other.quantity
        self.fat_qty += other.fat_qty
        self.snf_qty += other.snf_qty
        self.amount += other.amount
        self.manual_quantity |= other.manual_quantity
        self.manual_fat |= other.manual_fat

    def summary(self) -> dict[str, float]:
        q = self.quantity
        amt = self.amount
        return {
            "manual_quantity": self.manual_quantity,
            "manual_fat": self.manual_fat,
            "quantity": truncate_float(q, 2),
            "fat": truncate_float(self.fat_qty / q, 2) if q else 0.0,
            "snf": truncate_float(self.snf_qty / q, 2) if q else 0.0,
            "fat_kg": truncate_float(self.fat_qty / 100, 3),
            "snf_kg": truncate_float(self.snf_qty / 100, 3),
            "rate": truncate_float(amt / q, 2) if q else 0.0,
            "amount": truncate_float(amt, 2),
        }


# Rate is not differenced: a rate gap is already reflected in the amount gap
_METRICS = ("quantity", "fat", "snf", "fat_kg", "snf_kg", "amount")


def _diff(received: dict[str, float], dispatched: dict[str, float]) -> dict[str, float]:
    """Received minus dispatched; negative means the MCC got less."""
    return {
        k: truncate_float(received[k] - dispatched[k], 3 if k.endswith("_kg") else 2)
        for k in _METRICS
    }


class MccBillComparisonExecutor(ReportExecutor):
    __slots__ = ("_database", "_rate_chart_handler")

    def __init__(self, database, rate_chart_handler: RateChartHandler) -> None:
        self._database = database
        self._rate_chart_handler = rate_chart_handler

    async def execute(self, query: ReportQuery) -> ReportResult:
        if not query.vlcc_id:
            raise ValueError("Please select a VLCC to generate the Milk Bill Comparison.")

        session = self._database.session
        m, d = MccCollectionModel, DispatchModel

        mcc = await self.get_mcc(session, query.mcc_id)
        vlcc = await self._get_vlcc_with_mobile(session, query.vlcc_id)

        # =========================================================
        # MCC receipts
        # =========================================================
        received_stmt = (
            select(
                m.collected_at,
                m.shift,
                m.quantity,
                m.fat_percent,
                m.snf_percent,
                m.total_amount,
                m.rank,
                m.milk_type,
                m.quantity_collection_mode,
                m.measurement_mode,
            )
            .where(
                *self.filters(m, query),
                m.vlcc_id == query.vlcc_id,
            )
            .order_by(m.collected_at, m.id)
        )

        # =========================================================
        # VLCC dispatches for the same window
        # =========================================================
        dispatch_stmt = (
            select(
                d.collected_at,
                d.shift,
                d.quantity,
                d.fat_percent,
                d.snf_percent,
                d.quantity_collection_mode,
                d.measurement_mode,
            )
            .where(
                d.vlcc_id == query.vlcc_id,
                self._date_filters(d, query, self.apply_filters()),
            )
        )

        received: dict[tuple[date, int], _Bucket] = defaultdict(_Bucket)
        # First MCC collection of a shift decides its chart rank and milk type
        shift_rank: dict[tuple[date, int], int] = {}
        shift_milk_type: dict[tuple[date, int], MilkType | None] = {}
        for row in (await session.execute(received_stmt)).mappings():
            key = self._shift_key(row["collected_at"], row["shift"])
            received[key].add(
                row["quantity"], row["fat_percent"], row["snf_percent"], row["total_amount"],
                manual_quantity=self.is_manual(row["quantity_collection_mode"]),
                manual_fat=self.is_manual(row["measurement_mode"]),
            )
            shift_rank.setdefault(key, row["rank"] or 1)
            shift_milk_type.setdefault(key, row["milk_type"])

        # =========================================================
        # Price each dispatch from the MCC's ranked rate charts
        # =========================================================
        charts = await self._get_assigned_charts(session, query.mcc_id)
        rate_cache: dict[tuple, float] = {}

        dispatched: dict[tuple[date, int], _Bucket] = defaultdict(_Bucket)
        for row in (await session.execute(dispatch_stmt)).mappings():
            key = self._shift_key(row["collected_at"], row["shift"])
            rate = await self._dispatch_rate(
                charts,
                rank=shift_rank.get(key, 1),
                fat=float(row["fat_percent"] or 0),
                snf=float(row["snf_percent"] or 0),
                milk_type=shift_milk_type.get(key),
                cache=rate_cache,
            )
            quantity = Decimal(row["quantity"] or 0)
            dispatched[key].add(
                quantity,
                row["fat_percent"],
                row["snf_percent"],
                quantity * Decimal(str(rate)),
                manual_quantity=self.is_manual(row["quantity_collection_mode"]),
                manual_fat=self.is_manual(row["measurement_mode"]),
            )

        # =========================================================
        # Build rows (chronological, morning before evening)
        # =========================================================
        rows: list[dict[str, Any]] = []
        total_received, total_dispatched = _Bucket(), _Bucket()

        for key in sorted(received.keys() | dispatched.keys()):
            rec = received.get(key, _Bucket())
            disp = dispatched.get(key, _Bucket())

            rec_summary = rec.summary()
            disp_summary = disp.summary()

            rows.append(
                {
                    "date": key[0].strftime("%d/%m/%y"),
                    "shift": "M" if key[1] == CollectionShift.MORNING else "E",
                    "dispatched": disp_summary,
                    "received": rec_summary,
                    "difference": _diff(rec_summary, disp_summary),
                    "is_dispatched": disp.quantity > 0,
                    "is_received": rec.quantity > 0,
                }
            )

            total_received.merge(rec)
            total_dispatched.merge(disp)

        received_total = total_received.summary()
        dispatched_total = total_dispatched.summary()

        return ReportResult(
            metadata=self.build_metadata(query, mcc, vlcc),
            report_type=query.report_type.value,
            header=self.headers,
            ledger=[
                LedgerResult(
                    head={
                        "Code": vlcc["vlcc_code"] if vlcc else "—",
                        "Name": vlcc["name"] if vlcc else "—",
                        "Mobile No": (vlcc["mobile"] if vlcc else None) or "—",
                    },
                    rows=rows,
                    footer={
                        "dispatched": dispatched_total,
                        "received": received_total,
                        "difference": _diff(received_total, dispatched_total),
                        "shifts": len(rows),
                        "missing_dispatch": sum(1 for r in rows if not r["is_dispatched"]),
                        "missing_receipt": sum(1 for r in rows if not r["is_received"]),
                    },
                )
            ],
            total=len(rows),
            footer={},
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return ["Qty", "FAT", "SNF", "FatKG", "SnfKG", "Rate", "Amount"]

    def apply_filters(self) -> AppliedOnFilters:
        return AppliedOnFilters(
            actor_type=Role.MCC,
            date_range=True,
            shift_range=True,
            mcc_id=True,
            is_deleted=True,
        )

    @staticmethod
    async def _get_assigned_charts(session, mcc_id) -> list[tuple[Any, MilkType | None]]:
        """MCC's active rate charts as (chart_id, milk_type); index 0 is rank 1."""
        stmt = (
            select(RateChartAssignmentModel.rate_chart_id, RateChartModel.milk_type)
            .join(RateChartModel, RateChartModel.id == RateChartAssignmentModel.rate_chart_id)
            .join(MccModel, MccModel.user_id == RateChartAssignmentModel.owner_id)
            .where(
                MccModel.id == mcc_id,
                RateChartAssignmentModel.is_active.is_(True),
            )
            .order_by(
                RateChartAssignmentModel.priority.asc(),
                RateChartAssignmentModel.created_at.asc(),
            )
        )
        return [(row.rate_chart_id, row.milk_type) for row in await session.execute(stmt)]

    async def _dispatch_rate(
        self,
        charts: list[tuple[Any, MilkType | None]],
        *,
        rank: int,
        fat: float,
        snf: float,
        milk_type: MilkType | None,
        cache: dict[tuple, float],
    ) -> float:
        """Rate for one dispatch; 0 when the MCC has no chart at that rank."""
        if not 1 <= rank <= len(charts):
            return 0.0
        chart_id, chart_milk_type = charts[rank - 1]
        milk_type = milk_type if milk_type is not None else chart_milk_type
        key = (chart_id, fat, snf, milk_type)
        if key not in cache:
            rate = await self._rate_chart_handler.get_rate_by_chart_id(chart_id, fat, snf, milk_type)
            cache[key] = truncate_float(rate, 2)
        return cache[key]

    @staticmethod
    def _shift_key(collected_at, shift) -> tuple[date, int]:
        return to_naive_ist(collected_at).date(), int(shift)

    @staticmethod
    async def _get_vlcc_with_mobile(session, vlcc_id):
        stmt = (
            select(
                VlccModel.name,
                VlccModel.vlcc_code,
                VlccModel.uic_code,
                UserModel.mobile,
            )
            .outerjoin(UserModel, UserModel.id == VlccModel.user_id)
            .where(VlccModel.id == vlcc_id)
        )
        return (await session.execute(stmt)).mappings().one_or_none()

    @staticmethod
    def build_metadata(query: ReportQuery, mcc, vlcc) -> ReportMetadata:
        return ReportMetadata(
            time=query.formatted_time,
            start_date=query.formatted_start_date,
            end_date=query.formatted_end_date,
            start_shift=query.formatted_start_shift,
            end_shift=query.formatted_end_shift,
            owner_name=mcc.get("owner_name") if mcc else None,
            role="mcc",
            report_name="Milk Bill Comparison",
            name=mcc.get("name", "—") if mcc else "—",
            code=mcc.get("code", "—") if mcc else "—",
            uic_code=vlcc.get("uic_code") if vlcc else None,
            address=(mcc.get("city") if mcc else None) or "—",
        )
