from app.modules.masters.route.domain.dto import RouteMasterDto
from uuid import UUID

from sqlalchemy import select, true, false, or_, exists
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.masters.route.domain.entities import RouteMaster
from app.modules.masters.route.domain.irepository import IRouteMasterRepository
from app.modules.masters.route.infrastructure.mapper import RouteMasterMapper
from app.modules.masters.route.infrastructure.models import RouteMasterModel
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.middleware.authentication import CurrentUser


class RouteMasterAccessScope:

    @staticmethod
    def condition(owner: CurrentUser):
        if owner.role_type == Role.SUPER_ADMIN:
            return true()

        same_role_condition = exists(
            select(1)
            .select_from(UserModel)
            .where(
                UserModel.id == RouteMasterModel.created_by,
                UserModel.role == owner.role,
            )
            .correlate(RouteMasterModel)
        )

        global_routes_condition = exists(
            select(1)
            .select_from(UserModel)
            .where(
                UserModel.id == RouteMasterModel.created_by,
                UserModel.role == Role.SUPER_ADMIN,
            )
            .correlate(RouteMasterModel)
        )

        hierarchy_condition = false()
        if owner.role_type == Role.ADMIN:
            parent_user = aliased(UserModel)
            hierarchy_condition = exists(
                select(1)
                .select_from(UserModel)
                .where(
                    UserModel.id == RouteMasterModel.created_by,
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
                .correlate(RouteMasterModel)
            )
        elif owner.role_type == Role.SUB_ADMIN:
            hierarchy_condition = exists(
                select(1)
                .select_from(UserModel)
                .where(
                    UserModel.id == RouteMasterModel.created_by,
                    UserModel.created_by == owner.id,
                )
                .correlate(RouteMasterModel)
            )

        return or_(
            RouteMasterModel.created_by == owner.id,
            global_routes_condition,
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


class RouteMasterRepository(IRouteMasterRepository):

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
        entity: RouteMaster,
    ) -> None:
        model = RouteMasterMapper.to_model(entity)
        self._session.add(model)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        entity: RouteMaster,
        owner: CurrentUser | None = None,
    ) -> None:
        stmt = select(RouteMasterModel).where(RouteMasterModel.id == entity.id)
        if owner is not None and owner.role_type != Role.SUPER_ADMIN:
            stmt = stmt.where(RouteMasterModel.created_by == owner.id)

        model = await self._session.scalar(stmt)
        if model is None:
            return

        model.route_code = entity.route_code
        model.route_name = entity.route_name
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
        stmt = select(RouteMasterModel).where(RouteMasterModel.id == id)
        if owner is not None and owner.role_type != Role.SUPER_ADMIN:
            stmt = stmt.where(RouteMasterModel.created_by == owner.id)

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
    ) -> RouteMaster | None:
        Creator = aliased(UserModel, name="creator")
        stmt = (
            select(RouteMasterModel, Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == RouteMasterModel.created_by)
            .where(RouteMasterModel.id == id)
        )
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.condition(owner))

        result = (await self._session.execute(stmt)).one_or_none()
        if result is None:
            return None
        return RouteMasterMapper.to_entity(result.RouteMasterModel, result.owner_name)

    # =========================================================
    # GET BY CODE
    # =========================================================

    async def get_by_code(
        self,
        code: int,
        owner: CurrentUser | None = None,
    ) -> RouteMaster | None:
        Creator = aliased(UserModel, name="creator")
        stmt = (
            select(RouteMasterModel, Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == RouteMasterModel.created_by)
            .where(RouteMasterModel.route_code == code)
        )
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.condition(owner))
        result = (await self._session.execute(stmt)).one_or_none()
        if result is None:
            return None
        return RouteMasterMapper.to_entity(result.RouteMasterModel, result.owner_name)

    # =========================================================
    # EXISTS CODE
    # =========================================================

    async def exists_code(
        self,
        code: int,
        owner: CurrentUser | None = None,
    ) -> bool:
        stmt = select(RouteMasterModel.id).where(RouteMasterModel.route_code == code)
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
    ) -> list[RouteMaster]:
        Creator = aliased(UserModel, name="creator")
        can_modify = RouteMasterAccessScope.can_modify(owner, RouteMasterModel.created_by)
        stmt = (
            select(RouteMasterModel, Creator.name.label("owner_name"), can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == RouteMasterModel.created_by)
        )
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.condition(owner))

        stmt = (
            stmt.order_by(RouteMasterModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [RouteMasterMapper.to_entity(row.RouteMasterModel, row.owner_name, getattr(row, 'can_modify', False)) for row in result]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser | None = None,
    ) -> list[RouteMaster]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(offset=offset, limit=limit, owner=owner)

        pattern = f"%{keyword}%"
        Creator = aliased(UserModel, name="creator")
        can_modify = RouteMasterAccessScope.can_modify(owner, RouteMasterModel.created_by)
        stmt = (
            select(RouteMasterModel, Creator.name.label("owner_name"), can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == RouteMasterModel.created_by)
            .where(RouteMasterModel.route_name.ilike(pattern))
        )
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.condition(owner))

        stmt = (
            stmt.order_by(RouteMasterModel.route_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [RouteMasterMapper.to_entity(row.RouteMasterModel, row.owner_name, getattr(row, 'can_modify', False)) for row in result]

    # =========================================================
    # COUNT
    # =========================================================

    async def count(self, owner: CurrentUser | None = None) -> int:
        from sqlalchemy import func
        stmt = select(func.count(RouteMasterModel.id))
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.condition(owner))
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
        stmt = select(func.count(RouteMasterModel.id)).where(
            RouteMasterModel.route_name.ilike(pattern)
        )
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.condition(owner))
        return await self._session.scalar(stmt) or 0


    async def get_routes_by_owner(self, owner_id: UUID) -> list[RouteMasterDto]:
        stmt = (
            select(RouteMasterModel)
            .where(RouteMasterModel.created_by == owner_id)
        )
        result = await self._session.execute(stmt)
        return [RouteMasterMapper.to_short_dto(row.RouteMasterModel) for row in result]