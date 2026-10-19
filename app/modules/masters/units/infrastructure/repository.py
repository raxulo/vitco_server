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
from app.middleware.authentication import CurrentUser


class UnitMasterAccessScope:

    @staticmethod
    def condition(owner: CurrentUser):
        if owner.role_type == Role.SUPER_ADMIN:
            return true()

        same_role_condition = exists(
            select(1)
            .select_from(UserModel)
            .where(
                UserModel.id == UnitMasterModel.created_by,
                UserModel.role == owner.role,
            )
            .correlate(UnitMasterModel)
        )

        global_units_condition = exists(
            select(1)
            .select_from(UserModel)
            .where(
                UserModel.id == UnitMasterModel.created_by,
                UserModel.role == Role.SUPER_ADMIN,
            )
            .correlate(UnitMasterModel)
        )

        hierarchy_condition = false()
        if owner.role_type == Role.ADMIN:
            parent_user = aliased(UserModel)
            hierarchy_condition = exists(
                select(1)
                .select_from(UserModel)
                .where(
                    UserModel.id == UnitMasterModel.created_by,
                    or_(
                        UserModel.created_by == owner.id,
                        exists(
                            select(1)
                            .select_from(parent_user)
                            .where(
                                parent_user.id == UserModel.created_by,
                                parent_user.created_by == owner.id,
                            )
                        )
                    )
                )
                .correlate(UnitMasterModel)
            )
        elif owner.role_type == Role.SUB_ADMIN:
            hierarchy_condition = exists(
                select(1)
                .select_from(UserModel)
                .where(
                    UserModel.id == UnitMasterModel.created_by,
                    UserModel.created_by == owner.id,
                )
                .correlate(UnitMasterModel)
            )

        return or_(
            UnitMasterModel.created_by == owner.id,
            global_units_condition,
            same_role_condition,
            hierarchy_condition
        )

    @staticmethod
    def can_modify(owner: CurrentUser | None, item_created_by):
        if owner is None:
            return false()
        role = owner.role_type

        # SuperAdmin -> everything
        if role == Role.SUPER_ADMIN:
            return true()

        # Admin -> own + direct SubAdmin/MCC/VLCC
        if role == Role.ADMIN:
            return or_(
                item_created_by == owner.id,
                exists(
                    select(1)
                    .select_from(UserModel)
                    .where(
                        UserModel.id == item_created_by,
                        UserModel.created_by == owner.id,
                        UserModel.role.in_((Role.SUB_ADMIN, Role.MCC, Role.VLCC)),
                    )
                ),
            )

        # SubAdmin -> own + own MCC/VLCC
        if role == Role.SUB_ADMIN:
            return or_(
                item_created_by == owner.id,
                exists(
                    select(1)
                    .select_from(UserModel)
                    .where(
                        UserModel.id == item_created_by,
                        UserModel.created_by == owner.id,
                        UserModel.role.in_((Role.MCC, Role.VLCC)),
                    )
                ),
            )

        # MCC / VLCC -> own only
        if role in (Role.MCC, Role.VLCC):
            return item_created_by == owner.id

        return false()


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
        if owner is not None and owner.role_type != Role.SUPER_ADMIN:
            stmt = stmt.where(UnitMasterModel.created_by == owner.id)

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
        if owner is not None and owner.role_type != Role.SUPER_ADMIN:
            stmt = stmt.where(UnitMasterModel.created_by == owner.id)

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