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
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.middleware.authentication import CurrentUser


class RouteMasterAccessScope:
    """
    Route codes follow the same hierarchy as rate charts (see `Hierarchy`):

    - View: Super Admin routes -> everyone; otherwise the creator, everyone
      below it and everyone above it. Another Admin's tree never sees them.
    - Modify / delete: the creator and everyone above it.
    - Create: only Super Admin, Admin and Sub Admin (`CREATOR_ROLES`).
    """

    CREATOR_ROLES = (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN)

    @staticmethod
    def condition(owner: CurrentUser):
        return Hierarchy.shared_visible(owner, RouteMasterModel.created_by)

    @staticmethod
    def can_modify(owner: CurrentUser | None, item_created_by):
        return Hierarchy.shared_modifiable(owner, item_created_by)


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
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.can_modify(owner, RouteMasterModel.created_by))

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
        if owner is not None:
            stmt = stmt.where(RouteMasterAccessScope.can_modify(owner, RouteMasterModel.created_by))

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