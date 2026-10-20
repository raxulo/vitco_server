from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, true, false, or_, exists
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.masters.units.domain.entities import UnitMaster
from app.modules.masters.units.domain.irepository import IUnitMasterRepository
from app.modules.masters.units.infrastructure.mapper import UnitMasterMapper
from app.modules.masters.units.infrastructure.models import UnitMasterModel
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.middleware.authentication import CurrentUser


class UnitMasterAccessScope:
    """Same hierarchy as route codes / rate charts — rules in `Hierarchy.shared_*`."""

    @staticmethod
    def condition(owner: CurrentUser):
        return Hierarchy.shared_visible(owner, UnitMasterModel.created_by)

    @staticmethod
    def can_modify(owner: CurrentUser | None, item_created_by):
        return Hierarchy.shared_modifiable(owner, item_created_by)


class UnitMasterRepository(IUnitMasterRepository):

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
    # CREATE
    # =========================================================

    async def create(
        self,
        entity: UnitMaster,
    ) -> None:
        model = UnitMasterMapper.to_model(entity)
        self._session.add(model)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        entity: UnitMaster,
        owner: CurrentUser | None = None,
    ) -> None:
        stmt = select(UnitMasterModel).where(UnitMasterModel.id == entity.id)
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.can_modify(owner, UnitMasterModel.created_by))

        model = await self._session.scalar(stmt)
        if model is None:
            return

        model.name = entity.name
        model.is_active = entity.is_active
        model.updated_at = entity.updated_at

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        id: UUID,
        owner: CurrentUser | None = None,
    ) -> None:
        stmt = select(UnitMasterModel).where(UnitMasterModel.id == id)
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.can_modify(owner, UnitMasterModel.created_by))

        model = await self._session.scalar(stmt)
        if model is not None:
            await self._session.delete(model)

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        id: UUID,
        owner: CurrentUser | None = None,
    ) -> UnitMaster | None:
        Creator = aliased(UserModel, name="creator")
        can_modify = UnitMasterAccessScope.can_modify(owner, UnitMasterModel.created_by)
        stmt = (
            select(UnitMasterModel, Creator.name.label("owner_name"), can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == UnitMasterModel.created_by)
            .where(UnitMasterModel.id == id)
        )
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))

        result = (await self._session.execute(stmt)).one_or_none()
        if result is None:
            return None
        return UnitMasterMapper.to_entity(result.UnitMasterModel, result.owner_name, result.can_modify)

    # =========================================================
    # GET BY NAME
    # =========================================================

    async def get_by_name(
        self,
        name: str,
        owner: CurrentUser | None = None,
    ) -> UnitMaster | None:
        Creator = aliased(UserModel, name="creator")
        can_modify = UnitMasterAccessScope.can_modify(owner, UnitMasterModel.created_by)
        stmt = (
            select(UnitMasterModel, Creator.name.label("owner_name"), can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == UnitMasterModel.created_by)
            .where(UnitMasterModel.name == name)
        )
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))
        result = (await self._session.execute(stmt)).one_or_none()
        if result is None:
            return None
        return UnitMasterMapper.to_entity(result.UnitMasterModel, result.owner_name, result.can_modify)

    # =========================================================
    # EXISTS NAME
    # =========================================================

    async def exists_name(
        self,
        name: str,
        owner: CurrentUser | None = None,
    ) -> bool:
        stmt = select(UnitMasterModel.id).where(UnitMasterModel.name == name)
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))
        result = await self._session.scalar(stmt)
        return result is not None

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser | None = None,
    ) -> list[UnitMaster]:
        Creator = aliased(UserModel, name="creator")
        can_modify = UnitMasterAccessScope.can_modify(owner, UnitMasterModel.created_by)
        stmt = (
            select(UnitMasterModel, Creator.name.label("owner_name"), can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == UnitMasterModel.created_by)
        )
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))

        stmt = (
            stmt.order_by(UnitMasterModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [UnitMasterMapper.to_entity(row.UnitMasterModel, row.owner_name, getattr(row, 'can_modify', False)) for row in result]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser | None = None,
    ) -> list[UnitMaster]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(offset=offset, limit=limit, owner=owner)

        pattern = f"%{keyword}%"
        Creator = aliased(UserModel, name="creator")
        can_modify = UnitMasterAccessScope.can_modify(owner, UnitMasterModel.created_by)
        stmt = (
            select(UnitMasterModel, Creator.name.label("owner_name"), can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == UnitMasterModel.created_by)
            .where(UnitMasterModel.name.ilike(pattern))
        )
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))

        stmt = (
            stmt.order_by(UnitMasterModel.name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [UnitMasterMapper.to_entity(row.UnitMasterModel, row.owner_name, getattr(row, 'can_modify', False)) for row in result]

    # =========================================================
    # COUNT
    # =========================================================

    async def count(self, owner: CurrentUser | None = None) -> int:
        from sqlalchemy import func
        stmt = select(func.count(UnitMasterModel.id))
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))
        return await self._session.scalar(stmt) or 0

    # =========================================================
    # COUNT SEARCH
    # =========================================================

    async def count_search(
        self,
        keyword: str,
        owner: CurrentUser | None = None,
    ) -> int:
        from sqlalchemy import func
        keyword = keyword.strip()
        pattern = f"%{keyword}%"
        stmt = select(func.count(UnitMasterModel.id)).where(
            UnitMasterModel.name.ilike(pattern)
        )
        if owner is not None:
            stmt = stmt.where(UnitMasterAccessScope.condition(owner))
        return await self._session.scalar(stmt) or 0