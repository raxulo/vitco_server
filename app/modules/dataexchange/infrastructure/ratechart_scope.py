"""
Rate Chart Scope for Prodata Exchange

Resolves and checks permissions for Prodata rate chart export and import (REQ-17, REQ-18):
- Export requires read access (Hierarchy.shared_visible)
- Import requires modify access (Hierarchy.shared_modifiable)
- Options lists visible Prodata charts with can_modify flag

Python 3.13+
"""

from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.common.settings.infrastructure.permissions import can_edit_rate_charts, rate_chart_limit
from app.modules.dataexchange.domain.exceptions import (
    ExcelExchangeForbiddenException,
    ExcelTargetNotFoundException,
    ExcelTargetRequiredException,
)
from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)
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

    async def create_chart_for_import(
        self,
        owner: CurrentUser,
        *,
        chart_name: str | None,
        milk_type: MilkType | int | str = MilkType.MIXED,
        effective_from: date | None = None,
        dry_run: bool = False,
    ) -> RateChartModel | None:
        if owner.role_type == Role.FARMER:
            raise ExcelExchangeForbiddenException("Farmers cannot create rate charts")

        if not await can_edit_rate_charts(self._session, owner):
            raise ExcelExchangeForbiddenException("You do not have permission to create rate charts")

        clean_name = (chart_name or "").strip()
        if not clean_name:
            raise ExcelTargetRequiredException("Rate chart name is required to create a new chart")

        parsed_milk_type = self._parse_milk_type(milk_type)

        limit = await rate_chart_limit(self._session, owner)
        if limit is not None:
            used = int(
                await self._session.scalar(
                    select(func.count(RateChartModel.id)).where(RateChartModel.created_by == owner.id)
                )
                or 0
            )
            if used >= limit:
                raise ExcelExchangeForbiddenException(
                    f"You can create at most {limit} rate chart{'s' if limit != 1 else ''}. You already have {used}."
                )

        if dry_run:
            return None

        start_date = effective_from or now_naive_ist().date()
        chart = RateChartModel(
            id=uuid4(),
            chart_name=clean_name,
            chart_type=RateChartType.PRODATA,
            milk_type=parsed_milk_type,
            calculation_type=RateCalculationType.FAT_AND_SNF,
            effective_from=start_date,
            effective_to=None,
            status=RateChartStatus.ACTIVE,
            created_by=owner.id,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
            description="Created via Excel Import",
        )
        self._session.add(chart)
        await self._session.flush()
        return chart

    @staticmethod
    def _parse_milk_type(value: MilkType | int | str | None) -> MilkType:
        if value is None:
            return MilkType.MIXED
        if isinstance(value, MilkType):
            return value
        if isinstance(value, int):
            try:
                return MilkType(value)
            except ValueError:
                return MilkType.MIXED
        if isinstance(value, str):
            clean = value.strip().upper()
            if clean in MilkType.__members__:
                return MilkType[clean]
            if clean.isdigit():
                try:
                    return MilkType(int(clean))
                except ValueError:
                    return MilkType.MIXED
        return MilkType.MIXED
