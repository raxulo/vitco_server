from ast import stmt
from app.modules.common.bank.infrastructure.mapper import BankAccountMapper
from app.modules.common.address.infrastructure.mapper import AddressMapper
from app.modules.common.address.domain.entities import Address
from app.modules.vlcc.domain.dto import VlccForMccDto
from app.modules.vlcc.domain.dto import VlccWithAllDetailsForMccDto
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.masters.route.infrastructure.models import RouteMasterModel
from app.modules.masters.route.domain.entities import RouteMaster
from sqlalchemy import true, delete, exists, false, or_, select, func, update
from app.modules.administration.domain.enums import Role
from app.middleware.authentication import CurrentUser
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.config.settings import Settings
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.vlcc.domain.entities import VlccRelations
from app.modules.vlcc.application.command import UpdateVlccCommand
from app.modules.vlcc.application.command import CreateVlcc
from idna import check_label
import uuid
from app.modules.vlcc.application.command import CreateVlccCommand
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.database.manager import DatabaseManager
from app.modules.vlcc.domain.entities import Vlcc
from app.modules.vlcc.domain.irepository import IVlccRepository
from app.modules.vlcc.infrastructure.mapper import VlccMapper
from app.modules.vlcc.infrastructure.models import VlccModel
from app.core.clock import now_naive_ist


class VlccAccessScope:
    """Which VLCCs a user may see / modify — rules in `Hierarchy`."""

    @staticmethod
    def condition(owner: CurrentUser):
        """VLCCs the owner may see (an MCC: only the VLCCs it created)."""
        vlcc_ids = Hierarchy.vlcc_ids(owner)
        return true() if vlcc_ids is None else VlccModel.id.in_(vlcc_ids)

    @staticmethod
    def modify_condition(owner: CurrentUser):
        """VLCCs the owner may update / delete."""
        vlcc_ids = Hierarchy.vlcc_ids(owner)
        return true() if vlcc_ids is None else VlccModel.id.in_(vlcc_ids)

    @staticmethod
    def supplier_condition(owner: CurrentUser):
        """VLCCs offered in the MCC collection form: an MCC also gets its creator's VLCCs."""
        vlcc_ids = Hierarchy.visible_vlcc_ids(owner)
        return true() if vlcc_ids is None else VlccModel.id.in_(vlcc_ids)

    @staticmethod
    def can_modify(owner: CurrentUser | None, item_created_by):
        if owner is None:
            return false()
        role = owner.role_type

        if role == Role.SUPER_ADMIN:
            return true()

        # Admin / Sub Admin / MCC -> VLCCs created within their hierarchy.
        # A VLCC user only views its own VLCC.
        if role in (Role.ADMIN, Role.SUB_ADMIN, Role.MCC):
            return item_created_by.in_(Hierarchy.vlcc_creators(owner))

        return false()


class VlccRepository(IVlccRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        vlcc: CreateVlcc,
        owner: CurrentUser | None = None,
    ) -> UUID:
        if owner is not None and owner.role_type not in {
            Role.SUPER_ADMIN,
            Role.ADMIN,
            Role.SUB_ADMIN,
            Role.MCC,
        }:
            raise PermissionError("VLCC creation is not allowed")

        model = VlccMapper.to_model(data=vlcc)

        if owner is not None:
            model.created_by = owner.id

        self._session.add(model)
        return model.id

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        entity: Vlcc,
        owner: CurrentUser | None = None,
    ) -> None:
        access = VlccAccessScope.modify_condition(owner) if owner else true()

        stmt = (
            update(VlccModel)
            .where(VlccModel.id == entity.id)
        )
        if owner:
            stmt = stmt.where(or_(VlccModel.user_id == owner.id, access))

        await self._session.execute(
            stmt.values(
                uic_code=entity.uic_code,
                vlcc_code=entity.vlcc_code,
                name=entity.name,
                contact_person=entity.contact_person,
                address_id=entity.address_id,
                bank_account_id=entity.bank_account_id,
                milk_quality_config_id=entity.milk_quality_config_id,
                settings_id=entity.settings_id,
                entry_mode=entity.entry_mode,
                route_code=entity.route_code,
                soc_percentage=entity.soc_percentage,
                farmer_enabled=entity.farmer_enabled,
                is_active=entity.is_active,
                is_deleted=entity.is_deleted,
                assigned_chart_rank=entity.assigned_chart_rank,
                updated_at=now_naive_ist(),
            )
        )

    async def update_by_command_data(
        self,
        data: UpdateVlccCommand,
        owner: CurrentUser | None = None,
    ) -> None:
        access = VlccAccessScope.modify_condition(owner) if owner else true()

        stmt = (
            update(VlccModel)
            .where(VlccModel.id == data.id)
        )
        if owner:
            stmt = stmt.where(or_(VlccModel.user_id == owner.id, access))

        await self._session.execute(
            stmt.values(
                uic_code=data.uic_code,
                vlcc_code=data.vlcc_code,
                name=data.name,
                contact_person=data.contact_person,
                address_id=data.address_id,
                bank_account_id=data.bank_account_id,
                milk_quality_config_id=data.milk_quality_config_id,
                settings_id=data.settings_id,
                profile_image=data.profile_image,
                entry_mode=data.entry_mode,
                route_code=data.route_code,
                soc_percentage=data.soc_percentage,
                farmer_enabled=data.farmer_enabled,
                is_active=data.is_active,
                assigned_chart_rank=data.assigned_chart_rank,
                updated_at=now_naive_ist(),
            )
        )

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> bool:
        stmt = (
            delete(VlccModel)
            .where(
                VlccModel.id == id,
                VlccAccessScope.modify_condition(owner),
            )
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    # =========================================================
    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        id: UUID,
        owner: CurrentUser | None = None,
    ) -> Vlcc | None:
        can_modify = VlccAccessScope.can_modify(owner, VlccModel.created_by) if owner else false()
        stmt = (
            select(
                VlccModel,
                RouteMasterModel.route_name,
                UserModel.profile_url,
                can_modify.label("can_modify"),
                AddressModel.city.label("city"),
            )
            .outerjoin(RouteMasterModel, RouteMasterModel.route_code == VlccModel.route_code)
            .outerjoin(UserModel, UserModel.id == VlccModel.user_id)
            .outerjoin(AddressModel, or_(AddressModel.user_id == VlccModel.user_id, AddressModel.id == VlccModel.address_id))
            .where(
                VlccModel.id == id,
            )
        )
        if owner is not None:
            stmt = stmt.where(VlccAccessScope.condition(owner))

        result = await self._session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            return None
        return VlccMapper.to_entity(
            row.VlccModel,
            route_name=row.route_name,
            profile_image=row.profile_url,
            can_modify=getattr(row, "can_modify", False),
            city=getattr(row, "city", None),
        )

    # =========================================================
    # GET BY CODE
    # =========================================================

    async def get_by_code(
        self,
        code: str,
        owner: CurrentUser | None = None,
    ) -> UUID | None:
        stmt = (
            select(VlccModel.id)
            .where(
                VlccModel.vlcc_code == code,
                VlccModel.is_deleted.is_(False),
            )
        )
        if owner is not None:
            stmt = stmt.where(VlccAccessScope.condition(owner))

        result = await self._session.scalar(stmt)
        return result

    async def get_by_uic_code(
        self,
        code: str,
        owner: CurrentUser | None = None,
    ) -> UUID | None:
        stmt = (
            select(VlccModel.id)
            .where(
                VlccModel.uic_code == code,
                VlccModel.is_deleted.is_(False),
            )
        )
        if owner is not None:
            stmt = stmt.where(VlccAccessScope.condition(owner))

        result = await self._session.scalar(stmt)
        return result

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
        Is this VLCC code already used in the owner's line (itself, above, below)?
        Another Admin's tree may hold the same code (see `Hierarchy.code_conflict`).
        """
        stmt = (
            select(VlccModel.id)
            .where(
                VlccModel.vlcc_code == code.strip(),
                VlccModel.is_deleted.is_(False),
                Hierarchy.code_conflict(owner, VlccModel.created_by),
            )
            .limit(1)
        )
        if exclude_id is not None:
            stmt = stmt.where(VlccModel.id != exclude_id)
        result = await self._session.scalar(stmt)
        return result is not None

    # =========================================================
    # EXISTS USER
    # =========================================================

    async def exists_user(self, user_id: UUID) -> bool:
        stmt = select(VlccModel.id).where(VlccModel.user_id == user_id).limit(1)
        result = await self._session.scalar(stmt)
        return result is not None

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser,
    ) -> list[Vlcc]:
        from sqlalchemy.orm import aliased
        creator_alias = aliased(UserModel)
        user_alias = aliased(UserModel)
        can_modify = VlccAccessScope.can_modify(owner, VlccModel.created_by)
        result = await self._session.execute(
            select(
                VlccModel, 
                SettingsModel, 
                creator_alias.name.label("owner_name"), 
                user_alias.profile_url,
                can_modify.label("can_modify"),
                AddressModel.city.label("city"),
            )
            .join(creator_alias, creator_alias.id == VlccModel.created_by)
            .outerjoin(user_alias, user_alias.id == VlccModel.user_id)
            .outerjoin(AddressModel, or_(AddressModel.user_id == VlccModel.user_id, AddressModel.id == VlccModel.address_id))
            .join(SettingsModel, SettingsModel.id == VlccModel.settings_id)
            .where(
                VlccModel.is_deleted.is_(False),
                VlccAccessScope.condition(owner),
            )
            .order_by(VlccModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        return [
            VlccMapper.to_entity(
                row.VlccModel, 
                row.owner_name, 
                row.SettingsModel, 
                profile_image=row.profile_url,
                can_modify=getattr(row, "can_modify", False),
                city=getattr(row, "city", None),
            )
            for row in result
        ]

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser,
    ) -> list[Vlcc]:
        keyword = keyword.strip()
        if not keyword:
            return await self.list(offset=offset, limit=limit, owner=owner)

        pattern = f"%{keyword}%"
        can_modify = VlccAccessScope.can_modify(owner, VlccModel.created_by)
        stmt = (
            select(VlccModel, UserModel.profile_url, can_modify.label("can_modify"), AddressModel.city.label("city"))
            .outerjoin(UserModel, UserModel.id == VlccModel.user_id)
            .outerjoin(AddressModel, or_(AddressModel.user_id == VlccModel.user_id, AddressModel.id == VlccModel.address_id))
            .where(
                VlccModel.is_deleted.is_(False),
                UserModel.is_deleted.is_(False),
                VlccAccessScope.condition(owner),
            )
            .where(
                VlccModel.vlcc_code.ilike(pattern)
                | VlccModel.uic_code.ilike(pattern)
                | VlccModel.name.ilike(pattern)
            )
            .order_by(VlccModel.name.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            VlccMapper.to_entity(
                row.VlccModel, 
                profile_image=row.profile_url,
                can_modify=getattr(row, "can_modify", False),
                city=getattr(row, "city", None),
            ) 
            for row in result.all()
        ]

    # =========================================================
    # COUNT
    # =========================================================

    async def count(self, owner: CurrentUser) -> int:
        stmt = (
            select(func.count(VlccModel.id))
            .where(
                VlccModel.is_deleted.is_(False),
                VlccAccessScope.condition(owner),
            )
        )
        return await self._session.scalar(stmt) or 0

    # =========================================================
    # COUNT SEARCH
    # =========================================================

    async def count_search(
        self,
        keyword: str,
        owner: CurrentUser,
    ) -> int:
        keyword = keyword.strip()
        pattern = f"%{keyword}%"
        stmt = (
            select(func.count(VlccModel.id))
            .where(
                VlccModel.is_deleted.is_(False),
                VlccAccessScope.condition(owner),
            )
            .where(
                VlccModel.vlcc_code.ilike(pattern)
                | VlccModel.uic_code.ilike(pattern)
                | VlccModel.name.ilike(pattern)
            )
        )
        return await self._session.scalar(stmt) or 0

    async def get_relations(self, vlcc_id: UUID) -> VlccRelations | None:
        row = (
            await self._session.execute(
                select(
                    VlccModel.id,
                    VlccModel.user_id,
                    VlccModel.address_id,
                    VlccModel.bank_account_id,
                    VlccModel.settings_id,
                    VlccModel.milk_quality_config_id,
                ).where(VlccModel.id == vlcc_id)
            )
        ).one_or_none()

        return VlccRelations(*row) if row else None

    async def get_vlccs_by_mcc(self, mcc_id: UUID) -> list[Vlcc]:
        result = await self._session.scalars(
            select(VlccModel)
            .join(MccModel, MccModel.created_by == VlccModel.created_by)
            .where(MccModel.id == mcc_id)
            .order_by(VlccModel.created_at.desc())
        )

        return [VlccMapper.to_entity(model) for model in result]

    async def get_vlccs_half_detail_by_mcc(self, mcc_id: UUID, owner: CurrentUser | None = None):
        # An MCC's VLCCs: created by the MCC user, or by whoever created the MCC
        mcc_creators = select(MccModel.user_id).where(MccModel.id == mcc_id).union(
            select(MccModel.created_by).where(MccModel.id == mcc_id)
        )
        stmt = (
            select(
                VlccModel,
                UserModel,
                AddressModel,
                BankAccountModel,
            )
            .outerjoin(
                UserModel,
                UserModel.id == VlccModel.user_id,
            )
            .outerjoin(
                AddressModel,
                AddressModel.id == VlccModel.address_id,
            )
            .outerjoin(
                BankAccountModel,
                BankAccountModel.id == VlccModel.bank_account_id,
            )
            .where(
                VlccModel.created_by.in_(mcc_creators),
                VlccModel.is_deleted.is_(False),
                # ...and only those the logged-in user may collect from
                *([VlccAccessScope.supplier_condition(owner)] if owner is not None else []),
            )
            .order_by(VlccModel.created_at.desc())
        )

        result = await self._session.execute(stmt)
        return result