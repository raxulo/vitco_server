# app/modules/dashboard/infrastructure/repository.py
"""
Dashboard read model.

Every query is scoped with the same AccessScope rules the module list
screens use, so a user's dashboard never shows more than they can open.
Collections are read from one of two "sources": VLCC collections (farmer ->
VLCC) or MCC collections (VLCC -> MCC).
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.collections.mcc_collection.infrastructure.models import (
    MccCollectionModel,
)
from app.modules.collections.mcc_collection.infrastructure.repository import (
    MccCollectionAccessScope,
)
from app.modules.collections.vlcc_collection.infrastructure.models import (
    DispatchModel,
    VlccCollectionModel,
)
from app.modules.collections.vlcc_collection.infrastructure.repository import (
    VlccCollectionAccessScope,
)
from app.modules.dashboard.application.dto import (
    CollectionTotals,
    RankRow,
    RecentRow,
)
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.farmer.infrastructure.repository import FarmerAccessScope
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.mcc.infrastructure.repository import MccAccessScope
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.vlcc.infrastructure.repository import VlccAccessScope


@dataclass(frozen=True, slots=True)
class CollectionSource:
    """A collection table plus the owner-scoped conditions that apply to it."""

    model: Any
    conditions: tuple


class DashboardRepository:

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # Sources
    # =========================================================

    @staticmethod
    def vlcc_collections(owner: CurrentUser) -> CollectionSource:
        m = VlccCollectionModel
        return CollectionSource(
            model=m,
            conditions=(m.is_deleted.is_(False), VlccCollectionAccessScope.condition(owner)),
        )

    @staticmethod
    def mcc_collections(owner: CurrentUser, *, exclude_weight: bool = False) -> CollectionSource:
        m = MccCollectionModel
        conditions = [m.is_deleted.is_(False), MccCollectionAccessScope.condition(owner)]
        if exclude_weight:
            # Weight MCCs only weigh milk (no FAT / SNF); their quantity is kept out of the total
            conditions.append(
                m.mcc_id.not_in(select(MccModel.id).where(MccModel.mcc_type == MccType.WEIGHT))
            )
        return CollectionSource(model=m, conditions=tuple(conditions))

    # =========================================================
    # Collection aggregates
    # =========================================================

    async def totals(
        self,
        source: CollectionSource,
        start: datetime,
        end: datetime,
        *,
        party_column: str = "vlcc_id",
    ) -> CollectionTotals:
        m = source.model
        row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                    func.coalesce(func.sum(m.total_amount), 0).label("amount"),
                    func.coalesce(func.sum(m.quantity * m.fat_percent), 0).label("fat_qty"),
                    func.coalesce(func.sum(m.quantity * m.snf_percent), 0).label("snf_qty"),
                    func.count(m.id).label("entries"),
                    func.count(func.distinct(getattr(m, party_column))).label("parties"),
                    func.count(func.distinct(func.date(m.collected_at))).label("days"),
                ).where(*self._window(source, start, end))
            )
        ).one()
        return CollectionTotals(
            quantity=float(row.quantity),
            amount=float(row.amount),
            fat_qty=float(row.fat_qty),
            snf_qty=float(row.snf_qty),
            entries=row.entries,
            parties=row.parties,
            days=row.days,
        )

    async def daily(
        self,
        source: CollectionSource,
        start: datetime,
        end: datetime,
    ) -> dict[date, tuple[float, float]]:
        """Quantity and amount per calendar day."""
        m = source.model
        day = func.date(m.collected_at)
        rows = await self._session.execute(
            select(
                day.label("day"),
                func.coalesce(func.sum(m.quantity), 0).label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
            )
            .where(*self._window(source, start, end))
            .group_by(day)
        )
        return {self._as_date(r.day): (float(r.quantity), float(r.amount)) for r in rows}

    async def quantity_by(
        self,
        source: CollectionSource,
        start: datetime,
        end: datetime,
        column: str,
    ) -> dict[Any, float]:
        """Quantity grouped by an enum column such as `shift` or `milk_type`."""
        m = source.model
        col = getattr(m, column)
        rows = await self._session.execute(
            select(col.label("key"), func.coalesce(func.sum(m.quantity), 0).label("quantity"))
            .where(*self._window(source, start, end))
            .group_by(col)
        )
        return {r.key: float(r.quantity) for r in rows}

    async def top_vlccs(
        self,
        source: CollectionSource,
        start: datetime,
        end: datetime,
        *,
        limit: int = 6,
    ) -> tuple[RankRow, ...]:
        m, v = source.model, VlccModel
        qty = func.coalesce(func.sum(m.quantity), 0)
        rows = await self._session.execute(
            select(
                v.vlcc_code.label("code"),
                v.name.label("name"),
                qty.label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
            )
            .join(v, v.id == m.vlcc_id)
            .where(*self._window(source, start, end))
            .group_by(v.id, v.vlcc_code, v.name)
            .order_by(qty.desc())
            .limit(limit)
        )
        return tuple(RankRow(code=r.code, name=r.name, quantity=float(r.quantity), amount=float(r.amount)) for r in rows)

    async def top_farmers(
        self,
        source: CollectionSource,
        start: datetime,
        end: datetime,
        *,
        limit: int = 6,
    ) -> tuple[RankRow, ...]:
        m, f, u = source.model, FarmerModel, UserModel
        qty = func.coalesce(func.sum(m.quantity), 0)
        rows = await self._session.execute(
            select(
                f.farmer_code.label("code"),
                u.name.label("name"),
                qty.label("quantity"),
                func.coalesce(func.sum(m.total_amount), 0).label("amount"),
            )
            .join(f, f.id == m.farmer_id)
            .outerjoin(u, u.id == f.user_id)
            .where(*self._window(source, start, end))
            .group_by(f.id, f.farmer_code, u.name)
            .order_by(qty.desc())
            .limit(limit)
        )
        return tuple(RankRow(code=r.code, name=r.name or "—", quantity=float(r.quantity), amount=float(r.amount)) for r in rows)

    async def recent(
        self,
        source: CollectionSource,
        *,
        party: str,
        limit: int = 8,
    ) -> tuple[RecentRow, ...]:
        """Latest entries; `party` is "vlcc" or "farmer" (who the milk came from)."""
        m = source.model
        if party == "farmer":
            code_col, name_col = FarmerModel.farmer_code, UserModel.name
            stmt = (
                select(m, code_col.label("code"), name_col.label("name"))
                .join(FarmerModel, FarmerModel.id == m.farmer_id)
                .outerjoin(UserModel, UserModel.id == FarmerModel.user_id)
            )
        else:
            stmt = select(m, VlccModel.vlcc_code.label("code"), VlccModel.name.label("name")).join(
                VlccModel, VlccModel.id == m.vlcc_id
            )
        rows = await self._session.execute(
            stmt.where(*source.conditions).order_by(m.collected_at.desc()).limit(limit)
        )
        result = []
        for r in rows:
            entry = r[0]
            result.append(
                RecentRow(
                    collected_at=entry.collected_at,
                    shift=int(entry.shift),
                    code=r.code,
                    name=r.name or "—",
                    quantity=float(entry.quantity or 0),
                    fat=float(entry.fat_percent or 0),
                    snf=float(entry.snf_percent or 0),
                    amount=float(entry.total_amount or 0),
                )
            )
        return tuple(result)

    # =========================================================
    # Entity counts
    # =========================================================

    async def count_mccs(self, owner: CurrentUser) -> int:
        return await self._count(MccModel, MccModel.is_deleted.is_(False), MccAccessScope.condition(owner))

    async def count_vlccs(self, owner: CurrentUser) -> int:
        conditions = [VlccModel.is_deleted.is_(False)]
        if owner.role_type in (Role.VLCC, Role.VLCC_FARMER):
            conditions.append(VlccModel.user_id == owner.id)
        else:
            conditions.append(VlccAccessScope.condition(owner))
        return await self._count(VlccModel, *conditions)

    async def count_farmers(self, owner: CurrentUser) -> int:
        conditions = [FarmerModel.is_deleted.is_(False)]
        if owner.role_type == Role.VLCC:
            conditions.append(
                FarmerModel.vlcc_id.in_(select(VlccModel.id).where(VlccModel.user_id == owner.id))
            )
        else:
            conditions.append(FarmerAccessScope.condition(owner))
        return await self._count(FarmerModel, *conditions)

    async def dispatch_quantity(self, owner: CurrentUser, start: datetime, end: datetime) -> float:
        """Milk the VLCC user dispatched to the MCC in the window."""
        d = DispatchModel
        value = await self._session.scalar(
            select(func.coalesce(func.sum(d.quantity), 0))
            .join(VlccModel, VlccModel.id == d.vlcc_id)
            .where(
                VlccModel.user_id == owner.id,
                d.collected_at >= start,
                d.collected_at < end,
            )
        )
        return float(value or 0)

    # =========================================================
    # Scope labels
    # =========================================================

    async def scope_label(self, owner: CurrentUser) -> str | None:
        """Name of the unit an MCC / VLCC / farmer user operates, for the header."""
        role = owner.role_type
        if role == Role.MCC:
            row = (await self._session.execute(
                select(MccModel.name, MccModel.code).where(MccModel.user_id == owner.id)
            )).first()
            return f"{row.name} ({row.code})" if row else None
        if role in (Role.VLCC, Role.VLCC_FARMER):
            row = (await self._session.execute(
                select(VlccModel.name, VlccModel.vlcc_code).where(VlccModel.user_id == owner.id)
            )).first()
            return f"{row.name} ({row.vlcc_code})" if row else None
        if role == Role.FARMER:
            row = (await self._session.execute(
                select(FarmerModel.farmer_code, VlccModel.name)
                .outerjoin(VlccModel, VlccModel.id == FarmerModel.vlcc_id)
                .where(FarmerModel.user_id == owner.id)
            )).first()
            return f"Code {row.farmer_code} · {row.name or '—'}" if row else None
        return None

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _window(source: CollectionSource, start: datetime, end: datetime) -> tuple:
        m = source.model
        return (*source.conditions, m.collected_at >= start, m.collected_at < end)

    async def _count(self, model, *conditions) -> int:
        return int(await self._session.scalar(select(func.count(model.id)).where(*conditions)) or 0)

    @staticmethod
    def _as_date(value) -> date:
        # SQLite returns func.date() as text, PostgreSQL as a date
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
