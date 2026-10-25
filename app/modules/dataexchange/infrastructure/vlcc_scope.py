"""
VLCC Scope for Farmer Exchange

Which VLCC a user may export / import farmers for (DECISION-004), resolved
on the server whatever the client sends:

    VLCC login          -> its own VLCC, locked
    MCC / Sub Admin /
    Admin               -> VLCCs in its hierarchy (Hierarchy.vlcc_ids)
    Super Admin         -> every VLCC
    Farmer              -> not allowed

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
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
from app.modules.farmer.infrastructure.repository import FarmerRepository
from app.modules.vlcc.infrastructure.models import VlccModel


@dataclass(slots=True, frozen=True)
class VlccOption:

    id: UUID
    code: str
    name: str


@dataclass(slots=True, frozen=True)
class VlccOptions:

    items: list[VlccOption]
    total: int
    locked: bool
    default_id: UUID | None


class VlccScope:

    __slots__ = ("_database", "_farmers")

    def __init__(self, database: DatabaseManager, farmer_repository: FarmerRepository) -> None:
        self._database = database
        self._farmers = farmer_repository

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    async def options(self, owner: CurrentUser, *, search: str | None, limit: int, offset: int) -> VlccOptions:
        self._ensure_role(owner)
        conditions = self._conditions(owner)
        keyword = (search or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(or_(VlccModel.vlcc_code.ilike(pattern), VlccModel.name.ilike(pattern)))

        total = int(await self._session.scalar(select(func.count(VlccModel.id)).where(*conditions)) or 0)
        rows = (await self._session.execute(
            select(VlccModel.id, VlccModel.vlcc_code, VlccModel.name)
            .where(*conditions)
            .order_by(VlccModel.vlcc_code, VlccModel.id)
            .offset(offset)
            .limit(limit)
        )).all()
        items = [VlccOption(id=row.id, code=row.vlcc_code, name=row.name) for row in rows]

        locked = owner.role_type is Role.VLCC
        default_id = items[0].id if (locked or total == 1) and items else None
        return VlccOptions(items=items, total=total, locked=locked, default_id=default_id)

    async def resolve(self, owner: CurrentUser, requested: UUID | None) -> VlccOption:
        """The VLCC this request acts on; a VLCC login always gets its own."""
        self._ensure_role(owner)
        conditions = self._conditions(owner)
        if owner.role_type is not Role.VLCC:
            if requested is None:
                raise ExcelTargetRequiredException()
            conditions.append(VlccModel.id == requested)
        row = (await self._session.execute(
            select(VlccModel.id, VlccModel.vlcc_code, VlccModel.name).where(*conditions).limit(1)
        )).first()
        if row is None:
            raise ExcelTargetNotFoundException()
        return VlccOption(id=row.id, code=row.vlcc_code, name=row.name)

    async def can_manage_farmers(self, owner: CurrentUser) -> bool:
        """Same rule as the farmer API: a VLCC needs its farmer permission."""
        return await self._farmers.can_manage_farmers(owner)

    # ---------------------------------------------------------

    @staticmethod
    def _ensure_role(owner: CurrentUser) -> None:
        if owner.role_type is Role.FARMER:
            raise ExcelExchangeForbiddenException()

    @staticmethod
    def _conditions(owner: CurrentUser) -> list:
        conditions = [VlccModel.is_deleted.is_(False)]
        if owner.role_type is Role.VLCC:
            conditions.append(VlccModel.user_id == owner.id)
        else:
            vlcc_ids = Hierarchy.vlcc_ids(owner)
            if vlcc_ids is not None:
                conditions.append(VlccModel.id.in_(vlcc_ids))
        return conditions
