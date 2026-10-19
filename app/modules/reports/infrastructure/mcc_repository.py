# infrastructure/repository.py

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.reports.application.dto import ReportResult
from app.modules.reports.application.queries import ReportQuery


class MccReportRepository:

    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession):
        self._session = session

    async def shift_summary(
        self,
        query: ReportQuery,
    ) -> ReportResult:

        m = MccCollectionModel

        filters = [
            m.is_deleted.is_(False),
        ]

        if query.dairy_id:
            filters.append(m.shop_id == query.dairy_id)

        if query.mcc_id:
            filters.append(m.mcc_id == query.mcc_id)

        if query.start_date:
            filters.append(
                m.collection_date >= query.start_date
            )

        if query.end_date:
            filters.append(
                m.collection_date < query.end_date
            )

        if query.shift is not None:
            filters.append(m.shift == query.shift)

        if query.milk_type is not None:
            filters.append(
                m.milk_type == query.milk_type
            )

        if query.route_code:
            filters.append(
                m.route_code == query.route_code
            )

        stmt = (
            select(
                func.date(
                    m.collection_date
                ).label("date"),

                m.shift,

                func.count(m.id).label(
                    "entries"
                ),

                func.coalesce(
                    func.sum(m.quantity),
                    0,
                ).label("quantity"),

                func.coalesce(
                    func.sum(m.amount),
                    0,
                ).label("amount"),

                func.coalesce(
                    func.avg(m.fat),
                    0,
                ).label("fat"),

                func.coalesce(
                    func.avg(m.snf),
                    0,
                ).label("snf"),

                func.count().over().label(
                    "total"
                ),
            )
            .where(*filters)
            .group_by(
                func.date(m.collection_date),
                m.shift,
            )
            .order_by(
                func.date(m.collection_date),
                m.shift,
            )
            .offset(query.offset)
            .limit(query.size)
        )

        result = await self._session.execute(stmt)

        rows = result.mappings().all()

        total = rows[0]["total"] if rows else 0

        return ReportResult(
            report_type=query.report_type.value,
            rows=[
                {
                    "date": row["date"],
                    "shift": row["shift"],
                    "entries": row["entries"],
                    "quantity": row["quantity"],
                    "amount": row["amount"],
                    "fat": row["fat"],
                    "snf": row["snf"],
                }
                for row in rows
            ],
            total=total,
        )