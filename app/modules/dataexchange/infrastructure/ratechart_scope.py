"""
Rate Chart Scope for Prodata Exchange

Resolves and checks permissions for Prodata rate chart export and import (REQ-17, REQ-18):
- Export requires read access (Hierarchy.shared_visible)
- Import requires modify access (Hierarchy.shared_modifiable)
- Options lists visible Prodata charts with can_modify flag

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.dataexchange.domain.exceptions import (
    ExcelExchangeForbiddenException,
    ExcelTargetNotFoundException,
    ExcelTargetRequiredException,
)
from app.modules.ratechart.domain.enums import RateChartType
from app.modules.ratechart.infrastructure.models import RateChartModel


@dataclass(slots=True, frozen=True)
class RateChartOption:
    id: UUID
    name: str
    milk_type: int
    calculation_type: int
    can_modify: bool


@dataclass(slots=True, frozen=True)
class RateChartOptions:
    items: list[RateChartOption]
    total: int


class RateChartScope:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    async def options(
        self,
        owner: CurrentUser,
        *,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> RateChartOptions:
        if owner.role_type == Role.FARMER:
            raise ExcelExchangeForbiddenException("Farmers cannot access rate chart exchange")

        visible_cond = Hierarchy.shared_visible(owner, RateChartModel.created_by)
        conditions = [
            RateChartModel.chart_type == RateChartType.PRODATA,
            visible_cond,
        ]

        keyword = (search or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(RateChartModel.chart_name.ilike(pattern))

        total = int(
            await self._session.scalar(
                select(func.count(RateChartModel.id)).where(*conditions)
            )
            or 0
        )

        can_modify_expr = Hierarchy.shared_modifiable(owner, RateChartModel.created_by)

        stmt = (
            select(
                RateChartModel.id,
                RateChartModel.chart_name,
                RateChartModel.milk_type,
                RateChartModel.calculation_type,
                can_modify_expr.label("can_modify"),
            )
            .where(*conditions)
            .order_by(RateChartModel.chart_name.asc(), RateChartModel.id)
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()

        items = [
            RateChartOption(
                id=row.id,
                name=row.chart_name,
                milk_type=int(row.milk_type.value if hasattr(row.milk_type, "value") else row.milk_type),
                calculation_type=int(row.calculation_type.value if hasattr(row.calculation_type, "value") else row.calculation_type),
                can_modify=bool(row.can_modify),
            )
            for row in rows
        ]

        return RateChartOptions(items=items, total=total)

    async def resolve_for_export(self, owner: CurrentUser, chart_id: UUID | None) -> RateChartModel:
        if chart_id is None:
            raise ExcelTargetRequiredException("Rate chart ID is required for export")

        chart = await self._session.scalar(
            select(RateChartModel).where(RateChartModel.id == chart_id)
        )
        if chart is None or chart.chart_type != RateChartType.PRODATA:
            raise ExcelTargetNotFoundException("The selected Prodata rate chart was not found")

        # Check visibility
        is_visible = await self._session.scalar(
            select(RateChartModel.id).where(
                RateChartModel.id == chart_id,
                Hierarchy.shared_visible(owner, RateChartModel.created_by),
            )
        )
        if not is_visible:
            raise ExcelExchangeForbiddenException("You do not have access to view this rate chart")

        return chart

    async def resolve_for_import(self, owner: CurrentUser, chart_id: UUID | None) -> RateChartModel:
        if chart_id is None:
            raise ExcelTargetRequiredException("Rate chart ID is required for import")

        chart = await self._session.scalar(
            select(RateChartModel).where(RateChartModel.id == chart_id)
        )
        if chart is None or chart.chart_type != RateChartType.PRODATA:
            raise ExcelTargetNotFoundException("The selected Prodata rate chart was not found")

        # Check modifiability
        is_modifiable = await self._session.scalar(
            select(RateChartModel.id).where(
                RateChartModel.id == chart_id,
                Hierarchy.shared_modifiable(owner, RateChartModel.created_by),
            )
        )
        if not is_modifiable:
            raise ExcelExchangeForbiddenException("You do not have permission to modify this rate chart")

        return chart
