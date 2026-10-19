
from app.modules.masters.items.domain.dto import ItemMasterRateDto
from operator import and_
from uuid import UUID

from sqlalchemy import select, true, false, or_, exists
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.masters.items.domain.entities import ItemMaster
from app.modules.masters.items.domain.irepository import IItemMasterRepository
from app.modules.masters.items.infrastructure.mapper import ItemMasterMapper
from app.modules.masters.items.infrastructure.models import ItemMasterModel
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.middleware.authentication import CurrentUser


class ItemMasterAccessScope:

    @staticmethod
    def condition(owner: CurrentUser):

        if owner.role_type == Role.SUPER_ADMIN:
            return true()

        same_role_condition = exists(
            select(1)
            .select_from(UserModel)
            .where(
                UserModel.id == ItemMasterModel.created_by,
                UserModel.role == owner.role,
            )
            .correlate(ItemMasterModel)
        )

        global_items_condition = exists(
            select(1)
            .select_from(UserModel)
            .where(
                UserModel.id == ItemMasterModel.created_by,
                UserModel.role == Role.SUPER_ADMIN,
            )
            .correlate(ItemMasterModel)
        )

        hierarchy_condition = false()
        if owner.role_type == Role.ADMIN:
            parent_user = aliased(UserModel)
            hierarchy_condition = exists(
                select(1)
                .select_from(UserModel)
                .where(
                    UserModel.id == ItemMasterModel.created_by,
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
                .correlate(ItemMasterModel)
            )
        elif owner.role_type == Role.SUB_ADMIN:
            hierarchy_condition = exists(
                select(1)
                .select_from(UserModel)
                .where(
                    UserModel.id == ItemMasterModel.created_by,
                    UserModel.created_by == owner.id,
                )
                .correlate(ItemMasterModel)
            )

        return or_(
            ItemMasterModel.created_by == owner.id,
            global_items_condition,
            same_role_condition,
            hierarchy_condition
        )

    # =========================================================
    # MODIFY ACCESS
    # =========================================================

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
                        UserModel.role.in_(
                            (
                                Role.SUB_ADMIN,
                                Role.MCC,
                                Role.VLCC,
                            )
                        ),
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
                        UserModel.role.in_(
                            (
                                Role.MCC,
                                Role.VLCC,
                            )
                        ),
                    )
                ),
            )

        # MCC / VLCC -> own only
        if role in (Role.MCC, Role.VLCC):
            return item_created_by == owner.id

        return false()

    @staticmethod
    def name_condition(owner: CurrentUser):
        role = owner.role_type

        # SUPER ADMIN -> own only
        if role == Role.SUPER_ADMIN:
            return ItemMasterModel.created_by == owner.id

        # ADMIN -> own + parent SuperAdmin
        if role == Role.ADMIN:
            return or_(
                ItemMasterModel.created_by == owner.id,

                ItemMasterModel.created_by == (
                    select(UserModel.created_by)
                    .where(UserModel.id == owner.id)
                    .scalar_subquery()
                ),
            )

        # SUB ADMIN -> own + parent Admin
        # parent Admin -> parent SuperAdmin
        if role == Role.SUB_ADMIN:
            parent_admin = (
                select(UserModel.created_by)
                .where(UserModel.id == owner.id)
                .scalar_subquery()
            )

            return or_(
                ItemMasterModel.created_by == owner.id,

                ItemMasterModel.created_by == parent_admin,

                ItemMasterModel.created_by == (
                    select(UserModel.created_by)
                    .where(UserModel.id == parent_admin)
                    .scalar_subquery()
                ),
            )

        # MCC / VLCC -> own + parent SubAdmin/Admin/SuperAdmin
        if role in (Role.MCC, Role.VLCC):
            parent = (
                select(UserModel.created_by)
                .where(UserModel.id == owner.id)
                .scalar_subquery()
            )

            admin = (
                select(UserModel.created_by)
                .where(UserModel.id == parent)
                .scalar_subquery()
            )

            return or_(
                ItemMasterModel.created_by == owner.id,
                ItemMasterModel.created_by == parent,
                ItemMasterModel.created_by == admin,

                ItemMasterModel.created_by == (
                    select(UserModel.created_by)
                    .where(UserModel.id == admin)
                    .scalar_subquery()
                ),
            )

        return false()

class ItemMasterRepository(IItemMasterRepository):

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
        entity: ItemMaster,
    ) -> None:
        model = ItemMasterMapper.to_model(entity)
        self._session.add(model)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        entity: ItemMaster,
        owner: CurrentUser | None = None,
    ) -> None:
        stmt = select(ItemMasterModel).where(ItemMasterModel.id == entity.id)
        if owner is not None and owner.role_type != Role.SUPER_ADMIN:
            stmt = stmt.where(ItemMasterModel.created_by == owner.id)

        model = await self._session.scalar(stmt)
        if model is None:
            return

        model.item_code = entity.item_code
        model.item_name = entity.item_name
        model.unit_id = entity.unit_id
        model.rate = entity.rate
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
        stmt = select(ItemMasterModel).where(ItemMasterModel.id == id)
        if owner is not None and owner.role_type != Role.SUPER_ADMIN:
            stmt = stmt.where(ItemMasterModel.created_by == owner.id)

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
    ) -> ItemMaster | None:
        Creator = aliased(UserModel, name="creator")
        stmt = (
            select(ItemMasterModel, Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == ItemMasterModel.created_by)
            .where(ItemMasterModel.id == id)
        )
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))

        result = (await self._session.execute(stmt)).one_or_none()
        if result is None:
            return None
        return ItemMasterMapper.to_entity(result.ItemMasterModel, result.owner_name)

    # =========================================================
    # GET BY CODE
    # =========================================================

    async def get_by_code(
        self,
        code: int,
        owner: CurrentUser | None = None,
    ) -> ItemMaster | None:
        Creator = aliased(UserModel, name="creator")
        stmt = (
            select(ItemMasterModel, Creator.name.label("owner_name"))
            .outerjoin(Creator, Creator.id == ItemMasterModel.created_by)
            .where(ItemMasterModel.item_code == code)
        )
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))
        result = (await self._session.execute(stmt)).one_or_none()
        if result is None:
            return None
        return ItemMasterMapper.to_entity(result.ItemMasterModel, result.owner_name)

    # =========================================================
    # EXISTS CODE
    # =========================================================

    async def exists_code(
        self,
        code: int,
        owner: CurrentUser | None = None,
    ) -> bool:
        stmt = select(ItemMasterModel.id).where(ItemMasterModel.item_code == code)
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))
        result = await self._session.scalar(stmt)
        return result is not None

    # =========================================================
    # EXISTS ITEM
    # =========================================================

    async def exists_item(
        self,
        item_name: str,
        item_code: int,
        owner: CurrentUser,
    ) -> bool:

        stmt = (
            select(ItemMasterModel.id)
            .where(
                or_(
                    ItemMasterModel.item_code == item_code,
                    (
                        ItemMasterModel.item_name == item_name.strip()
                    )
                    & ItemMasterAccessScope.name_condition(owner),
                )
            )
            .limit(1)
        )

        return await self._session.scalar(stmt) is not None

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser | None = None,
    ) -> list[ItemMaster]:
        Creator = aliased(UserModel, name="creator")
        can_modify = ItemMasterAccessScope.can_modify(owner, ItemMasterModel.created_by)
        stmt = (
            select(ItemMasterModel, Creator.name.label("owner_name"), 
                   can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == ItemMasterModel.created_by)
        )
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))

        stmt = (
            stmt.order_by(ItemMasterModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [ItemMasterMapper.to_entity(row.ItemMasterModel, row.owner_name, getattr(row, 'can_modify', False)) for row in result]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser | None = None,
    ) -> list[ItemMaster]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(offset=offset, limit=limit, owner=owner)

        pattern = f"%{keyword}%"
        Creator = aliased(UserModel, name="creator")
        can_modify = ItemMasterAccessScope.can_modify(owner, ItemMasterModel.created_by)
        stmt = (
            select(ItemMasterModel, Creator.name.label("owner_name"),
                   can_modify.label("can_modify"))
            .outerjoin(Creator, Creator.id == ItemMasterModel.created_by)
            .where(ItemMasterModel.item_name.ilike(pattern))
        )
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))

        stmt = (
            stmt.order_by(ItemMasterModel.item_name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [ItemMasterMapper.to_entity(row.ItemMasterModel, row.owner_name, getattr(row, 'can_modify', False)) for row in result]

    # =========================================================
    # COUNT
    # =========================================================

    async def count(self, owner: CurrentUser | None = None) -> int:
        from sqlalchemy import func
        stmt = select(func.count(ItemMasterModel.id))
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))
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
        stmt = select(func.count(ItemMasterModel.id)).where(
            ItemMasterModel.item_name.ilike(pattern)
        )
        if owner is not None:
            stmt = stmt.where(ItemMasterAccessScope.condition(owner))
        return await self._session.scalar(stmt) or 0


    async def get_by_ids(
        self,
        ids: list[UUID],
    ) -> list[ItemMasterRateDto]:
        """
        Fetch multiple items by their IDs efficiently.
        Use this for dropdowns where you already know the IDs.
        """
        if not ids:
            return []
        
        # If owner is provided, filter by access scope
        # (Assuming owner is passed as an argument in real implementation)
        # For now, returning without owner filtering based on user's request
        stmt = (
            select(ItemMasterModel.id, ItemMasterModel.rate)
            .where(ItemMasterModel.id.in_(ids))
        )
        
        result = await self._session.execute(stmt)
        return [ItemMasterRateDto(row.id, row.rate) for row in result]