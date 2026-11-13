from app.modules.mcc.domain.enums import MccType
from sqlalchemy import true, delete, exists, false, or_, select
from app.modules.media.domain import storage_interface
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.mcc.domain.entities import MccRelations
from app.modules.mcc.domain.dto import MccListDto
from app.modules.mcc.domain.dto import MccDto
from app.modules.mcc.domain.irepository import IMccRepository
from uuid import UUID
from sqlalchemy.orm import aliased
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.hierarchy import Hierarchy

from app.core.database.manager import DatabaseManager
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.mcc.infrastructure.mapper import MccMapper
from app.modules.mcc.infrastructure.models import MccModel


class MccAccessScope:
    """Which MCCs a user may see / modify — rules in `Hierarchy`."""

    @staticmethod
    def condition(owner: CurrentUser):
        mcc_ids = Hierarchy.mcc_ids(owner)
        return true() if mcc_ids is None else MccModel.id.in_(mcc_ids)

    @staticmethod
    def can_modify(owner: CurrentUser | None, item_created_by):
        if owner is None:
            return false()
        role = owner.role_type

        if role == Role.SUPER_ADMIN:
            return true()

        # Admin / Sub Admin -> MCCs created by themselves or (Admin) their Sub Admins.
        # An MCC user only views its own MCC.
        if role in (Role.ADMIN, Role.SUB_ADMIN):
            return item_created_by.in_(Hierarchy.managers(owner))

        return false()

class MccRepository(IMccRepository):

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:
        self._database = database

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        entity: Mcc,
        owner: CurrentUser | None = None
    ) -> None:
        if owner.role_type not in {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.SUB_ADMIN,
        }:
            raise PermissionError("MCC creation is not allowed")

        model = MccMapper.to_model(entity)

        if owner is not None:
            model.created_by = owner.id

        self._database.session.add(model)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        entity: Mcc,
        owner: CurrentUser | None = None,
    ) -> None:
        access = MccAccessScope.condition(owner)

        stmt = (
            select(MccModel)
            .where(
                MccModel.id == entity.id,
            )
            .where(or_(MccModel.user_id == owner.id, access))
        )

        model = await self._database.session.scalar(stmt)

        if model is None:
            return

        model.code = entity.code
        model.name = entity.name
        model.mcc_type = entity.mcc_type
        model.route_code = entity.route_code

        model.sample_start = entity.sample_start
        model.sample_end = entity.sample_end
        model.visible_member = entity.visible_member
        model.shift_delay = entity.shift_delay or "00:00"

        model.address_id = entity.address_id
        model.bank_account_id = entity.bank_account_id
        model.milk_quality_config_id = entity.milk_quality_config_id
        model.fixed_rate_config_id = entity.fixed_rate_config_id

        model.profile_image = entity.profile_image

        model.is_active = entity.is_active

        model.updated_by = entity.updated_by
        model.updated_at = entity.updated_at

        model.is_deleted = entity.is_deleted
        model.deleted_at = entity.deleted_at
        model.deleted_by = entity.deleted_by

    # =========================================================
    # DELETE
    # =========================================================
    async def delete(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> bool:

        stmt = (
            delete(MccModel)
            .where(
                MccModel.id == id,
                MccAccessScope.condition(owner),
            )
        )

        result = await self._database.session.execute(stmt)

        return result.rowcount > 0

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        id: UUID,
        owner: CurrentUser | None = None,
    ) -> Mcc | None:

        can_modify = MccAccessScope.can_modify(owner, MccModel.created_by)


        stmt = (
            select(MccModel, UserModel.profile_url, can_modify.label("can_modify"))
            .outerjoin(UserModel, UserModel.id == MccModel.user_id)
            .where(
                MccModel.id == id,
                MccModel.is_deleted.is_(False),
            )
        )
        if owner is not None:
            stmt = stmt.where(MccAccessScope.condition(owner))

        row = (await self._database.session.execute(stmt)).first()

        if row is None:
            return None

        return MccMapper.to_entity(row[0], profile_image=row[1], can_modify=row[2])

    # =========================================================
    # GET BY CODE
    # =========================================================

    async def get_by_code(
        self,
        code: str,
        owner: CurrentUser | None = None,
    ) -> Mcc | None:

        stmt = (
            select(MccModel, UserModel.profile_url)
            .outerjoin(UserModel, UserModel.id == MccModel.user_id)
            .where(
                MccModel.code == code,
                MccModel.is_deleted.is_(False),
            )
        )
        if owner is not None:
            stmt = stmt.where(MccAccessScope.condition(owner))
            
        stmt = stmt.limit(1)

        row = (await self._database.session.execute(stmt)).first()

        return MccMapper.to_entity(row[0], profile_image=row[1]) if row else None

    # =========================================================
    # EXISTS CODE
    # =========================================================

    async def exists_code(
        self,
        code: str,
        owner: CurrentUser,
        exclude_id: UUID | None = None,
    ) -> bool:
        """
        Is this MCC code already used in the owner's line (itself, above, below)?
        Another Admin's tree may hold the same code (see `Hierarchy.code_conflict`).
        """
        stmt = (
            select(MccModel.id)
            .where(
                MccModel.code == code.strip(),
                MccModel.is_deleted.is_(False),
                Hierarchy.code_conflict(owner, MccModel.created_by),
            )
            .limit(1)
        )
        if exclude_id is not None:
            stmt = stmt.where(MccModel.id != exclude_id)

        return (
            await self._database.session.scalar(stmt)
        ) is not None

    # =========================================================
    # EXISTS USER
    # =========================================================

    async def exists_user(
        self,
        user_id: UUID,
    ) -> bool:

        stmt = (
            select(MccModel.id)
            .where(
                MccModel.user_id == user_id,
                MccModel.is_deleted.is_(False),
            )
            .limit(1)
        )

        result = await self._database.session.scalar(stmt)

        return result is not None

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        offset: int,
        limit: int,
        keyword: str | None,
        owner: CurrentUser,
    ) -> list[Mcc]:

        stmt = (
            select(MccModel, UserModel.profile_url)
            .outerjoin(UserModel, UserModel.id == MccModel.user_id)
            .where(
                MccModel.is_deleted.is_(False),
                MccAccessScope.condition(owner),
            )
        )

        if keyword:
            pattern = f"%{keyword.strip()}%"

            stmt = stmt.where(
                or_(
                    MccModel.code.ilike(pattern),
                    MccModel.name.ilike(pattern),
                )
            )

        stmt = (
            stmt
            .order_by(MccModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self._database.session.execute(stmt)

        return [
            MccMapper.to_entity(row[0], profile_image=row[1])
            for row in result.all()
        ]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[Mcc]:

        keyword = keyword.strip()

        if not keyword:
            return await self.list(
                offset=offset,
                limit=limit,
                keyword=None,
                owner=CurrentUser(id=None, role=str(Role.SUPER_ADMIN.value)), # Dummy owner to bypass check if list is called
            )

        pattern = f"%{keyword}%"

        stmt = (
            select(MccModel, UserModel.profile_url)
            .outerjoin(UserModel, UserModel.id == MccModel.user_id)
            .where(
                MccModel.is_deleted.is_(False),
                (
                    MccModel.code.ilike(pattern)
                    |
                    MccModel.name.ilike(pattern)
                ),
            )
            .order_by(
                MccModel.name.asc(),
            )
            .offset(offset)
            .limit(limit)
        )

        result = await self._database.session.execute(stmt)

        return [
            MccMapper.to_entity(row[0], profile_image=row[1])
            for row in result.all()
        ]

    async def count(
        self,
        owner: CurrentUser | None = None,
        manager: CurrentUser | None = None,
    ) -> int:

        from sqlalchemy import func

        stmt = (
            select(func.count(MccModel.id))
            .where(
                MccModel.is_deleted.is_(False),
                *self._manager_conditions(manager),
            )
        )
        if owner:
            stmt = stmt.where(MccAccessScope.condition(owner))

        return await self._database.session.scalar(stmt) or 0

    @staticmethod
    def _manager_conditions(manager: CurrentUser | None) -> list:
        """Filter to one Admin / Sub Admin's line of MCCs (the `Hierarchy` rules)."""
        if manager is None:
            return []
        mcc_ids = Hierarchy.mcc_ids(manager)
        return [] if mcc_ids is None else [MccModel.id.in_(mcc_ids)]

    # =========================================================
    # COUNT SEARCH
    # =========================================================

    async def count_search(
        self,
        keyword: str,
        owner: CurrentUser | None = None,
        manager: CurrentUser | None = None,
    ) -> int:

        from sqlalchemy import func

        keyword = keyword.strip()

        pattern = f"%{keyword}%"
        creator = aliased(UserModel, name="creator")

        # Same joins / conditions as `list_mcc_with_user`, so the page count matches the rows shown
        stmt = (
            select(func.count(MccModel.id))
            .join(UserModel, UserModel.id == MccModel.user_id)
            .outerjoin(creator, creator.id == MccModel.created_by)
            .where(
                MccModel.is_deleted.is_(False),
                self._search_condition(pattern, creator),
                *self._manager_conditions(manager),
            )
        )
        if owner:
            stmt = stmt.where(MccAccessScope.condition(owner))

        return await self._database.session.scalar(stmt) or 0

    @staticmethod
    def _search_condition(pattern: str, creator):
        """MCC search matches its name, its code, or the name of the user who created it."""
        return or_(
            MccModel.code.ilike(pattern),
            MccModel.name.ilike(pattern),
            creator.name.ilike(pattern),
        )


    async def list_mcc_with_user(
        self,
        offset: int,
        limit: int,
        keyword: str | None = None,
        owner: CurrentUser | None = None,
        manager: CurrentUser | None = None,
    ) -> list[MccListDto]:

        CreatorModel = aliased(UserModel, name="creator")
        can_modify = MccAccessScope.can_modify(owner, MccModel.created_by)

        stmt = (
            select(
                MccModel.id.label("mcc_id"),
                MccModel.code.label("code"),
                MccModel.name.label("name"),
                MccModel.mcc_type.label("mcc_type"),
                MccModel.route_code.label("route_code"),
                MccModel.is_active.label("is_active"),
                AddressModel.city.label("city"),
                UserModel.profile_url.label("profile_image"),
                UserModel.id.label("user_id"),
                UserModel.name.label("user_name"),
                UserModel.mobile.label("mobile"),
                UserModel.email.label("email"),
                CreatorModel.name.label("created_by_name"),
                can_modify.label("can_modify"),
            )
            .join(UserModel, UserModel.id == MccModel.user_id)
            .outerjoin(AddressModel, AddressModel.id == MccModel.address_id)
            .outerjoin(CreatorModel, CreatorModel.id == MccModel.created_by)
            .where(
                MccModel.is_deleted.is_(False),
                *self._manager_conditions(manager),
            )
        )
        if owner:
            stmt = stmt.where(MccAccessScope.condition(owner))
                
        if keyword:
            stmt = stmt.where(self._search_condition(f"%{keyword.strip()}%", CreatorModel))

        stmt = stmt.order_by(MccModel.created_at.desc()).offset(offset).limit(limit)

        result = await self._database.session.execute(stmt)

        return [
            MccListDto(
                id=row.mcc_id,
                code=row.code,
                name=row.name,
                mcc_type=row.mcc_type,
                is_active=row.is_active,
                profile_image=row.profile_image,
                user_id=row.user_id,
                user_name=row.user_name,
                mobile=row.mobile,
                email=row.email,
                created_by_name=row.created_by_name,
                can_modify=getattr(row, "can_modify", False),
                city=getattr(row, "city", None),
                route_code=getattr(row, "route_code", None),
            )
            for row in result.all()
        ]

    async def assigned_mcc_with_user(
        self,
        offset: int,
        limit: int,
        keyword: str | None = None,
        owner: CurrentUser | None = None,
    ) -> list[MccListDto]:

        CreatorModel = aliased(UserModel, name="creator")
        can_modify = MccAccessScope.can_modify(owner, MccModel.created_by)

        stmt = (
            select(
                MccModel.id.label("mcc_id"),
                MccModel.code.label("code"),
                MccModel.name.label("name"),
                MccModel.mcc_type.label("mcc_type"),
                MccModel.route_code.label("route_code"),
                MccModel.is_active.label("is_active"),
                AddressModel.city.label("city"),
                UserModel.profile_url.label("profile_image"),
                UserModel.id.label("user_id"),
                UserModel.name.label("user_name"),
                UserModel.mobile.label("mobile"),
                UserModel.email.label("email"),
                CreatorModel.name.label("created_by_name"),
                can_modify.label("can_modify"),
            )
            .join(UserModel, UserModel.id == MccModel.user_id)
            .outerjoin(AddressModel, AddressModel.id == MccModel.address_id)
            .outerjoin(CreatorModel, CreatorModel.id == MccModel.created_by)
            .where(
                MccModel.is_deleted.is_(False),
                MccModel.mcc_type != MccType.WEIGHT,
            )
        )
        if owner:
            stmt = stmt.where(MccAccessScope.condition(owner))
                
        if keyword:
            stmt = stmt.where(self._search_condition(f"%{keyword.strip()}%", CreatorModel))

        stmt = stmt.order_by(MccModel.created_at.desc()).offset(offset).limit(limit)

        result = await self._database.session.execute(stmt)

        return [
            MccListDto(
                id=row.mcc_id,
                code=row.code,
                name=row.name,
                mcc_type=row.mcc_type,
                is_active=row.is_active,
                profile_image=row.profile_image,
                user_id=row.user_id,
                user_name=row.user_name,
                mobile=row.mobile,
                email=row.email,
                created_by_name=row.created_by_name,
                can_modify=getattr(row, "can_modify", False),
                city=getattr(row, "city", None),
                route_code=getattr(row, "route_code", None),
            )
            for row in result.all()
        ]

    async def get_relations(self, mcc_id: UUID) -> MccRelations | None:
        result = await self._database.session.execute(
            select(
                MccModel.id,
                MccModel.user_id,
                MccModel.address_id,
                MccModel.bank_account_id,
                MccModel.settings_id,
                MccModel.milk_quality_config_id,
                MccModel.fixed_rate_config_id,
            )
            .where(MccModel.id == mcc_id)
        )

        row = result.one_or_none()

        return (
            MccRelations(*row)
            if row else None
        )