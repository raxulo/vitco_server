from sqlalchemy.orm import aliased
from sqlalchemy import alias
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.address.infrastructure.models import AddressModel
from sqlalchemy import true, false, exists, or_, delete, update, func, select
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.farmer.domain.entities import FarmerRelations
from app.modules.farmer.application.command import UpdateFarmer
from app.modules.farmer.application.command import CreateFarmer
from app.modules.administration.infrastructure.models import UserModel
from app.modules.vlcc.infrastructure.repository import VlccAccessScope
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.farmer.domain.entities import Farmer
from app.modules.farmer.domain.irepository import IFarmerRepository
from app.modules.farmer.infrastructure.mapper import FarmerMapper
from app.modules.farmer.infrastructure.models import FarmerModel


class FarmerAccessScope:

    @staticmethod
    def condition(owner: CurrentUser):
        if owner.role_type == Role.SUPER_ADMIN:
            return true()

        if owner.role_type == Role.FARMER:
            return FarmerModel.user_id == owner.id

        return exists(
            select(1)
            .select_from(VlccModel)
            .where(
                VlccModel.id == FarmerModel.vlcc_id,
                VlccAccessScope.condition(owner),
            )
            .correlate(FarmerModel)
        )

    @staticmethod
    def can_modify(owner: CurrentUser | None, farmer_vlcc_id):
        if owner is None:
            return false()
        role = owner.role_type

        # SuperAdmin -> everything
        if role == Role.SUPER_ADMIN:
            return true()

        # Check if they can modify the VLCC center
        return exists(
            select(1)
            .select_from(VlccModel)
            .where(
                VlccModel.id == farmer_vlcc_id,
                VlccAccessScope.can_modify(owner, VlccModel.created_by),
            )
            .correlate(FarmerModel)
        )


class FarmerRepository():

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

    async def create(self, data: CreateFarmer, owner: CurrentUser | None = None) -> UUID:
        farmer = Farmer.create(data)
        self._session.add(FarmerMapper.to_model(farmer))
        return farmer.id

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(self, data: UpdateFarmer, owner: CurrentUser) -> bool:
        values = data.changes()
        if not values:
            return False

        result = await self._session.execute(
            update(FarmerModel)
            .where(
                FarmerModel.id == data.id,
                FarmerAccessScope.condition(owner),
            )
            .values(**values)
        )

        return result.rowcount > 0

    async def update_entity(self, entity: Farmer, owner: CurrentUser) -> bool:
        result = await self._session.execute(
            update(FarmerModel)
            .where(
                FarmerModel.id == entity.id,
                FarmerAccessScope.condition(owner),
            )
            .values(
                farmer_code=entity.farmer_code,
                is_active=entity.is_active,
                is_deleted=entity.is_deleted,
                deleted_at=entity.deleted_at,
                deleted_by=entity.deleted_by,
            )
        )
        return result.rowcount > 0

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(self, farmer_id: UUID, owner: CurrentUser) -> bool:
        result = await self._session.execute(
            delete(FarmerModel)
            .where(
                FarmerModel.id == farmer_id,
                FarmerAccessScope.condition(owner),
            )
        )
        return result.rowcount > 0

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        farmer_id: UUID,
        owner: CurrentUser | None = None,
    ) -> Farmer | None:
        can_modify = FarmerAccessScope.can_modify(owner, FarmerModel.vlcc_id) if owner else false()
        stmt = (
            select(FarmerModel, UserModel.name, VlccModel.name, UserModel.profile_url, can_modify.label("can_modify"), UserModel.mobile.label("mobile"))
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .join(VlccModel, FarmerModel.vlcc_id == VlccModel.id)
            .where(
                FarmerModel.id == farmer_id,
                FarmerModel.is_deleted.is_(False),
            )
        )
        if owner is not None:
            stmt = stmt.where(FarmerAccessScope.condition(owner))

        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return FarmerMapper.to_entity(row[0], name=row[1], vlcc_name=row[2], profile_image=row[3], can_modify=getattr(row, "can_modify", False), mobile=getattr(row, "mobile", None))

    # =========================================================
    # GET BY CODE
    # =========================================================

    async def get_by_code(self, farmer_code: str, vlcc_id: UUID, owner: CurrentUser | None = None) -> Farmer | None:
        can_modify = FarmerAccessScope.can_modify(owner, FarmerModel.vlcc_id) if owner else false()
        stmt = (
            select(FarmerModel, UserModel.name, VlccModel.name, UserModel.profile_url, can_modify.label("can_modify"), UserModel.mobile.label("mobile"))
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .join(VlccModel, FarmerModel.vlcc_id == VlccModel.id)
            .where(
                FarmerModel.farmer_code == farmer_code,
                FarmerModel.vlcc_id == vlcc_id,
                FarmerModel.is_active.is_(True),
                FarmerModel.is_deleted.is_(False),
            )
        )
        if owner is not None:
            stmt = stmt.where(FarmerAccessScope.condition(owner))

        row = (await self._session.execute(stmt)).first()
        if row is None:
            return None
        return FarmerMapper.to_entity(row[0], name=row[1], vlcc_name=row[2], profile_image=row[3], can_modify=getattr(row, "can_modify", False), mobile=getattr(row, "mobile", None))

    # =========================================================
    # EXISTS CODE
    # =========================================================

    async def exists_code_in_vlcc(
        self,
        farmer_code: str,
        vlcc_id: UUID,
        owner: CurrentUser,
    ) -> bool:

        stmt = (
            select(FarmerModel.id)
            .where(
                FarmerModel.farmer_code == farmer_code.strip(),
                FarmerModel.vlcc_id == vlcc_id,
                FarmerModel.is_deleted.is_(False),
                FarmerAccessScope.condition(owner),
            )
            .limit(1)
        )

        return await self._session.scalar(stmt) is not None

    # =========================================================
    # EXISTS USER
    # =========================================================

    async def exists_user(self, user_id: UUID) -> bool:
        stmt = (
            select(FarmerModel.id)
            .where(
                FarmerModel.user_id == user_id,
                FarmerModel.is_deleted.is_(False),
            )
            .limit(1)
        )

        return await self._session.scalar(stmt) is not None

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self, *, offset: int, limit: int, 
        vlcc_id: UUID|None = None,
        owner: CurrentUser
    ) -> list[Farmer]:
        conditions = [
            FarmerModel.is_deleted.is_(False),
            FarmerAccessScope.condition(owner)
        ]

        if vlcc_id is not None:
            conditions.append(FarmerModel.vlcc_id == vlcc_id)
            conditions.append(VlccModel.id == vlcc_id)

        can_modify = FarmerAccessScope.can_modify(owner, FarmerModel.vlcc_id)
        stmt = (
            select(FarmerModel, UserModel.name, VlccModel.name, UserModel.profile_url, can_modify.label("can_modify"), UserModel.mobile.label("mobile"))
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .join(VlccModel, FarmerModel.vlcc_id == VlccModel.id)
            .where(*conditions)
            .order_by(FarmerModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = (await self._session.execute(stmt)).all()
        return [FarmerMapper.to_entity(row[0], name=row[1], vlcc_name=row[2], profile_image=row[3], can_modify=getattr(row, "can_modify", False), mobile=getattr(row, "mobile", None)) for row in result]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        vlcc_id: UUID|None = None,
        owner: CurrentUser | None = None
    ) -> list[Farmer]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(
                offset=offset, limit=limit, vlcc_id=vlcc_id, owner=owner
            )

        conditions = [
            FarmerModel.is_deleted.is_(False),
            FarmerAccessScope.condition(owner)
        ]
        if vlcc_id is not None:
            conditions.append(FarmerModel.vlcc_id == vlcc_id)

        pattern = f"%{keyword}%"
        can_modify = FarmerAccessScope.can_modify(owner, FarmerModel.vlcc_id)
        stmt = (
            select(FarmerModel, UserModel.name, VlccModel.name, UserModel.profile_url, can_modify.label("can_modify"), UserModel.mobile.label("mobile"))
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .join(VlccModel, FarmerModel.vlcc_id == VlccModel.id)
            .where(
                *conditions,
                FarmerModel.farmer_code.ilike(pattern) | UserModel.name.ilike(pattern)
            )
            .order_by(UserModel.name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = (await self._session.execute(stmt)).all()
        return [FarmerMapper.to_entity(row[0], name=row[1], vlcc_name=row[2], profile_image=row[3], can_modify=getattr(row, "can_modify", False), mobile=getattr(row, "mobile", None)) for row in result]

    # =========================================================
    # COUNT
    # =========================================================

    async def count(self, vlcc_id: UUID|None = None, owner: CurrentUser | None = None) -> int:
        from sqlalchemy import func
        conditions = [
            FarmerModel.is_deleted.is_(False),
            FarmerAccessScope.condition(owner)
        ]
        if vlcc_id is not None:
            conditions.append(FarmerModel.vlcc_id == vlcc_id)

        stmt = select(func.count(FarmerModel.id)).where(*conditions)
        return await self._session.scalar(stmt) or 0

    # =========================================================
    # COUNT SEARCH
    # =========================================================

    async def count_search(
        self,
        keyword: str,
        vlcc_id: UUID|None = None,
        owner: CurrentUser | None = None
    ) -> int:
        from sqlalchemy import func
        keyword = keyword.strip()
        conditions = [
            FarmerModel.is_deleted.is_(False),
            FarmerAccessScope.condition(owner)
        ]
        if vlcc_id is not None:
            conditions.append(FarmerModel.vlcc_id == vlcc_id)

        pattern = f"%{keyword}%"
        stmt = (
            select(func.count(FarmerModel.id))
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .where(
                *conditions,
                FarmerModel.farmer_code.ilike(pattern) | UserModel.name.ilike(pattern)
            )
        )
        return await self._session.scalar(stmt) or 0


    async def get_relations(self, farmer_id: UUID) -> FarmerRelations | None:
        result = await self._session.execute(
            select(
                FarmerModel.id,
                FarmerModel.user_id,
                FarmerModel.address_id,
                FarmerModel.bank_account_id,
                FarmerModel.assigned_chart_rank,
            )
            .where(FarmerModel.id == farmer_id)
        )

        row = result.one_or_none()

        return (
            FarmerRelations(*row)
            if row else None
        )

    async def get_farmers_full_detail_by_vlcc_id(self, vlcc_id: UUID):
        stmt = (
            select(
                FarmerModel,
                UserModel,
                AddressModel,
                BankAccountModel,
                VlccModel,
            )
            .join(
                VlccModel,
                VlccModel.id == FarmerModel.vlcc_id,
            )
            .outerjoin(
                UserModel,
                UserModel.id == FarmerModel.user_id,
            )
            .outerjoin(
                AddressModel,
                AddressModel.id == FarmerModel.address_id,
            )
            .outerjoin(
                BankAccountModel,
                BankAccountModel.id == FarmerModel.bank_account_id,
            )
            .where(
                FarmerModel.vlcc_id == vlcc_id,
                FarmerModel.is_deleted.is_(False),
            )
            .order_by(FarmerModel.created_at.desc())
        )

        result = await self._session.execute(stmt)
        return result.all()


    async def full_detail(
        self,
        farmer_id: UUID,
        owner: CurrentUser | None = None,
    ):

        VlccUser = aliased(UserModel, name="VlccUser")

        stmt = (
            select(
                FarmerModel,
                UserModel,
                VlccModel,
                VlccUser,
                AddressModel,
                BankAccountModel,
            )
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .join(VlccModel, FarmerModel.vlcc_id == VlccModel.id)
            .join(VlccUser, VlccModel.user_id == VlccUser.id)
            .outerjoin(AddressModel, FarmerModel.address_id == AddressModel.id)
            .outerjoin(
                BankAccountModel,
                FarmerModel.bank_account_id == BankAccountModel.id,
            )
            .where(
                FarmerModel.id == farmer_id,
                FarmerModel.is_deleted.is_(False),
            )
        )

        if owner is not None:
            stmt = stmt.where(FarmerAccessScope.condition(owner))

        row = (await self._session.execute(stmt)).first()

        if row is None:
            return None

        return row

    async def get_full_detail_by_code(
        self,
        farmer_code: str,
        vlcc_id: UUID,
        owner: CurrentUser | None = None,
    ):
        """
        Get full detailed row of a farmer via farmer_code and vlcc_id.
        Returns a tuple/row containing FarmerModel, UserModel, VlccModel, VlccUser, AddressModel, BankAccountModel.
        """
        VlccUser = aliased(UserModel, name="VlccUser")

        stmt = (
            select(
                FarmerModel,
                UserModel,
                VlccModel,
                VlccUser,
                AddressModel,
                BankAccountModel,
            )
            .join(UserModel, FarmerModel.user_id == UserModel.id)
            .join(VlccModel, FarmerModel.vlcc_id == VlccModel.id)
            .outerjoin(VlccUser, VlccModel.user_id == VlccUser.id)
            .outerjoin(AddressModel, FarmerModel.address_id == AddressModel.id)
            .outerjoin(
                BankAccountModel,
                FarmerModel.bank_account_id == BankAccountModel.id,
            )
            .where(
                FarmerModel.farmer_code == farmer_code.strip(),
                FarmerModel.vlcc_id == vlcc_id,
                FarmerModel.is_deleted.is_(False),
            )
        )

        if owner is not None:
            stmt = stmt.where(FarmerAccessScope.condition(owner))

        row = (await self._session.execute(stmt)).first()

        if row is None:
            return None

        return row

    async def full_detail_by_code(
        self,
        farmer_code: str,
        vlcc_id: UUID,
        owner: CurrentUser | None = None,
    ):
        """Alias for get_full_detail_by_code."""
        return await self.get_full_detail_by_code(farmer_code=farmer_code, vlcc_id=vlcc_id, owner=owner)

    async def get_full_detail_by_code_and_vlcc_id(
        self,
        farmer_code: str,
        vlcc_id: UUID,
        owner: CurrentUser | None = None,
    ):
        """Alias for get_full_detail_by_code."""
        return await self.get_full_detail_by_code(farmer_code=farmer_code, vlcc_id=vlcc_id, owner=owner)