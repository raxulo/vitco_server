from app.modules.reports.application.dto import LedgerResult
from sqlalchemy import select
from app.modules.reports.executors.base import ReportExecutor
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.administration.infrastructure.models import UserModel
from app.modules.collections.vlcc_collection.infrastructure.models import (
    VlccCollectionModel,
)
from app.modules.reports.application.dto import (
    ReportMetadata,
    ReportResult,
)
from app.modules.reports.application.queries import ReportQuery
from app.modules.administration.domain.enums import Role
from app.modules.reports.infrastructure.filters import AppliedOnFilters


class VlccDuplicateReceiptExecutor(ReportExecutor):
    __slots__ = ("_database",)

    def __init__(self, database) -> None:
        self._database = database

    async def execute(self, query: ReportQuery) -> ReportResult:
        # member_code of a VLCC report is the farmer code
        if not query.member_code:
            raise ValueError("Please enter the farmer code to print the duplicate receipt.")

        session = self._database.session
        m = VlccCollectionModel
        f = FarmerModel
        u = UserModel

        vlcc = await self.get_vlcc(session, query.vlcc_id)
        filters = self.filters(m, query)

        # Get farmer info
        farmer_name = "—"
        mobile_number = "—"
        farmer_stmt = (
            select(u.name, u.mobile)
            .select_from(f)
            .join(u, u.id == f.user_id)
            .where(f.farmer_code == query.member_code, f.vlcc_id == query.vlcc_id)
            .limit(1)
        )
        farmer_res = (await session.execute(farmer_stmt)).mappings().one_or_none()
        if farmer_res:
            farmer_name = farmer_res["name"]
            mobile_number = farmer_res["mobile"] or "—"

        rows_stmt = (
            select(
                m.collected_at.label("date_time"),
                f.farmer_code.label("code"),
                m.quantity.label("quantity"),
                m.fat_percent.label("fat"),
                m.snf_percent.label("snf"),
                m.rate_per_unit.label("rate"),
                m.total_amount.label("amount"),
            )
            .select_from(m)
            .join(f, f.id == m.farmer_id)
            .where(*filters)
        )

        rows_stmt = rows_stmt.where(f.farmer_code == query.member_code)

        rows_result = await session.execute(rows_stmt)

        rows = []
        for row in rows_result.mappings():
            rows.append({
                "time": row["date_time"].strftime("%H:%M") if row["date_time"] else "—",
                "code": row["code"],
                "quantity": row["quantity"],
                "fat": row["fat"],
                "snf": row["snf"],
                "rate": row["rate"],
                "amount": row["amount"],
            })

        return ReportResult(
            metadata=self.build_metadata(query, vlcc),
            report_type=query.report_type.value,
            header=self.headers,
            footer={},
            ledger=[
                LedgerResult(
                    head={
                        "Code": query.member_code,
                        "Name": farmer_name,
                        "Mobile No.": mobile_number,
                    },
                    rows=rows,
                )
            ],
            total=len(rows),
            page=query.page,
            size=query.size,
        )

    @property
    def headers(self) -> list[str]:
        return [
            "Time",
            "Code",
            "Qty.",
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
            member_code=True,
        )

    @staticmethod
    def build_metadata(
        query: ReportQuery,
        vlcc: dict | None,
    ) -> ReportMetadata:
        address = (vlcc.get("city") if vlcc else None) or "—"

        return ReportMetadata(
            time=query.formatted_time,
            date=query.formatted_start_date,
            start_shift=query.formatted_start_shift,
            start_code=query.member_code,
            role="vlcc",
            owner_name=vlcc.get("owner_name", None) if vlcc else None,
            report_name="Duplicate Receipt",
            name=vlcc.get("name", "—") if vlcc else "—",
            code=vlcc.get("vlcc_code", "—") if vlcc else "—",
            uic_code=vlcc.get("uic_code") if vlcc else None,
            address=address,
        )
