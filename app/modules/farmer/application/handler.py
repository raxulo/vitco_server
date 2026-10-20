from typing import Any
from app.modules.vlcc.domain.dto import VlccForFarmerDto
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.farmer.infrastructure.mapper import FarmerMapper
from unicodedata import name
from app.modules.administration.domain.entities import UserDto
from app.modules.farmer.domain.dto import FarmerFullDetailDto
from app.modules.common.bank.infrastructure.mapper import BankAccountMapper
from app.modules.common.address.infrastructure.mapper import AddressMapper
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.administration.infrastructure.models import UserModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.api.v1.schemas.sync import SubUserProfileSyncDto
from app.middleware.authentication import CurrentUser
from app.modules.farmer.application.command import DeleteFarmerQuery, DeleteFarmerCommand
from app.modules.farmer.application.command import ListFarmerQuery
from app.modules.farmer.application.command import GetFarmerQuery
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand
from dataclasses import asdict, is_dataclass
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.farmer.application.command import UpdateFarmerDetailCommand
from app.modules.farmer.application.command import CreateFarmerDetailCommand
from app.modules.farmer.application.command import UpdateFarmer
from app.modules.farmer.application.command import CreateFarmer
from app.modules.farmer.application.command import PartialUpdateFullDetailFarmer
from app.modules.common.profile.application.services import ProfileService
from app.core.clock import now_naive_ist

from datetime import datetime
from uuid import UUID, uuid4
from email_validator import validate_email

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.administration.domain.enums import Role
from app.modules.administration.domain.entities import User
from app.modules.administration.domain.exceptions import (
    UserNotFoundException,
    UserAlreadyExistsException,
)
from app.modules.administration.infrastructure.repository import UserRepository
from app.modules.farmer.domain.entities import Farmer
from app.modules.farmer.domain.exceptions import (
    FarmerNotFoundException,
    FarmerCodeAlreadyExistsException,
)
from app.modules.farmer.infrastructure.repository import FarmerRepository
from app.modules.farmer.domain.dto import FarmerDto, FarmerListDto


class FarmerHandler:

    __slots__ = (
        "_database",
        "_user_repository",
        "_farmer_repository",
        "_profile_service",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        user_repository: UserRepository,
        farmer_repository: FarmerRepository,
        profile_service: ProfileService
    ) -> None:
        self._database = database
        self._user_repository = user_repository
        self._farmer_repository = farmer_repository
        self._profile_service = profile_service

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self, command: CreateFarmer,
    ) -> bool:
        async with self._database.transaction():
            await self._ensure_code_available(command.farmer_code)
            await self._ensure_email_available(command.email)

            await self._farmer_repository.create(command)

        return True


    async def full_create(
        self, command: CreateFarmerDetailCommand,
        owner: CurrentUser
    ) -> bool:
        exists_farmer = await self._farmer_repository.exists_code_in_vlcc(command.farmer.farmer_code, command.farmer.vlcc_id, owner)
        if exists_farmer:
            raise FarmerCodeAlreadyExistsException()
        async with self._database.transaction():
            profile = await self._profile_service.create(
                user_data=command.user,
                address_data=command.address,
                bank_data=command.bank_account,
                role=Role.FARMER
            )
            await self._database.session.flush()
            farmer_data = CreateFarmer(
                user_id=profile.user.id,
                farmer_code=command.farmer.farmer_code,
                milk_type=command.farmer.milk_type,
                vlcc_id=command.farmer.vlcc_id,
                is_active=command.farmer.is_active,
                profile_image=command.farmer.profile_image,
                sms_enabled=command.farmer.sms_enabled,
                created_by=command.farmer.created_by,
                assigned_chart_rank=command.farmer.assigned_chart_rank if command.farmer.assigned_chart_rank is not None else 1,
                bank_account_id=profile.bank_account.id if profile.bank_account else None,
                address_id=profile.address.id if profile.address else None
            )
            await self._farmer_repository.create(farmer_data, owner)

        return True


    # =========================================================
    # UPDATE
    # =========================================================

    async def full_update(
        self, command: UpdateFarmerDetailCommand,
        owner: CurrentUser
    ) -> bool:
        relations = await self._farmer_repository.get_relations(command.farmer.id)
        if relations is None:
            raise FarmerNotFoundException()

        address_id = relations.address_id
        bank_account_id = relations.bank_account_id
        async with self._database.transaction():
            if not address_id and command.address:
                    address = await self._profile_service.create_address(
                        user_id=relations.user_id,
                        address_data=CreateAddressCommand(
                            **asdict(command.address)
                        ),
                    )
                    address_id = address.id
            if not bank_account_id:
                if command.bank_account:
                    bank_account = await self._profile_service.create_bank_account(
                        user_id=relations.user_id,
                        bank_data=CreateBankAccountCommand(
                            **asdict(command.bank_account)
                        ),
                    )
                    bank_account_id = bank_account.id

            # Flush the session to write the new Address/Bank Account rows to SQLite,
            # ensuring foreign key constraints do not fail during the update.
            await self._database.session.flush()

            await self._farmer_repository.update(data=
                UpdateFarmer(
                    address_id=address_id,
                    bank_account_id=bank_account_id,
                    **asdict(command.farmer)
                ), owner=owner
            )
            await self._profile_service.update(
                user_data=UpdateUserCommand(
                    id=relations.user_id,
                    **command.user.model_dump()
                ),
                address_data=UpdateAddressCommand(
                    id=address_id,
                    **asdict(command.address)
                ) if command.address else None,
                bank_data=UpdateBankAccountCommand(
                    id=bank_account_id,
                    **asdict(command.bank_account)
                ) if command.bank_account else None,
            )

        return True

    async def partial_update(
        self,
        command: PartialUpdateFullDetailFarmer,
        owner: CurrentUser,
    ) -> bool:
        relations = await self._farmer_repository.get_relations(owner.own_id)
        if relations is None:
            raise FarmerNotFoundException()

        address_id = relations.address_id
        bank_account_id = relations.bank_account_id

        async with self._database.transaction():
            # ---------------------------------------------
            # USER
            # ---------------------------------------------
            if command.user:
                await self._profile_service.update(
                    user_data=UpdateUserCommand(
                        id=relations.user_id,
                        name=command.user.name,
                        email=command.user.email,
                        mobile=command.user.mobile,
                        updated_by=command.updated_by,
                    )
                )

            # ---------------------------------------------
            # ADDRESS
            # ---------------------------------------------
            if command.address:
                address_data = asdict(command.address) if is_dataclass(command.address) else (command.address.model_dump(exclude_unset=True) if hasattr(command.address, "model_dump") else dict(command.address))
                if address_id:
                    await self._profile_service.address_update(
                        UpdateAddressCommand(
                            id=address_id,
                            **address_data,
                        )
                    )
                else:
                    address = await self._profile_service.create_address(
                        user_id=relations.user_id,
                        address_data=CreateAddressCommand(
                            **address_data,
                        ),
                    )
                    address_id = address.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # BANK ACCOUNT
            # ---------------------------------------------
            if command.bank_account:
                bank_data = asdict(command.bank_account) if is_dataclass(command.bank_account) else (command.bank_account.model_dump(exclude_unset=True) if hasattr(command.bank_account, "model_dump") else dict(command.bank_account))
                if bank_account_id:
                    await self._profile_service.bank_update(
                        UpdateBankAccountCommand(
                            id=bank_account_id,
                            **bank_data,
                        )
                    )
                else:
                    bank_account = await self._profile_service.create_bank_account(
                        user_id=relations.user_id,
                        bank_data=CreateBankAccountCommand(
                            **bank_data,
                        ),
                    )
                    bank_account_id = bank_account.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # FARMER
            # ---------------------------------------------
            if address_id != relations.address_id or bank_account_id != relations.bank_account_id:
                await self._farmer_repository.update(
                    data=UpdateFarmer(
                        id=relations.id,
                        address_id=address_id,
                        bank_account_id=bank_account_id,
                        updated_by=command.updated_by,
                    ),
                    owner=owner,
                )
                await self._database.session.flush()

        return True

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self, command: DeleteFarmerQuery,
    ) -> None:
        if command.owner is None:
            raise PermissionError("Owner context is required")
        async with self._database.transaction():
            farmer = await self._farmer_repository.get_by_id(command.id, command.owner)
            if farmer is None:
                raise FarmerNotFoundException()

            user = await self._profile_service._user_repository.get_by_id(farmer.user_id)
            if user is None:
                raise UserNotFoundException()

            await self._farmer_repository.update(
                UpdateFarmer(
                    id=farmer.id,
                    is_active=False
                ),
                command.owner,
            )

            user.is_active = False
            await self._profile_service._user_repository.update(user)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self, query: GetFarmerQuery,
    ) -> FarmerDto:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        farmer = await self._farmer_repository.get_by_id(query.id, query.owner)
        if farmer is None:
            raise FarmerNotFoundException()

        return self._to_dto(farmer)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteFarmerCommand,
    ) -> None:
        async with self._database.transaction():
            farmer = await self._farmer_repository.get_by_id(command.id, command.owner)
            if farmer is None:
                raise FarmerNotFoundException()

            user = await self._user_repository.get_by_id(farmer.user_id)
            if user is None:
                raise UserNotFoundException()

            now = now_naive_ist()

            # Soft delete user and free up email/mobile
            user.is_active = False
            user.is_deleted = True
            user.deleted_at = now
            user.deleted_by = command.deleted_by
            user.email = f"del_{uuid4().hex[:6]}_{user.email}"
            if user.mobile:
                user.mobile = f"del_{uuid4().hex[:6]}_{user.mobile}"

            # A deleted user's profile image is removed (file + media row)
            await self._profile_service.delete_profile_image(user.id)
            user.profile_image = None

            # Soft delete farmer and free up farmer_code
            freed_code = f"{farmer.farmer_code}__del_{farmer.id.hex[:6]}"
            farmer = Farmer(
                id=farmer.id,
                user_id=farmer.user_id,
                farmer_code=freed_code,
                vlcc_id=farmer.vlcc_id,
                address_id=farmer.address_id,
                bank_account_id=farmer.bank_account_id,
                assigned_chart_rank=farmer.assigned_chart_rank,
                milk_type=farmer.milk_type,
                profile_image=farmer.profile_image,
                sms_enabled=farmer.sms_enabled,
                is_active=False,
                created_by=farmer.created_by,
                created_at=farmer.created_at,
                updated_at=farmer.updated_at,
                name=farmer.name,
                vlcc_name=farmer.vlcc_name,
                can_modify=farmer.can_modify,
                is_deleted=True,
                deleted_at=now,
                deleted_by=command.deleted_by,
            )

            await self._user_repository.update(user)
            await self._farmer_repository.update_entity(farmer, command.owner)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListFarmerQuery,
    ) -> list[FarmerListDto]:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        if query.keyword:
            entities = await self._farmer_repository.search(
                keyword=query.keyword,
                offset=query.offset,
                limit=query.limit,
                vlcc_id=query.vlcc_id,
                owner=query.owner
            )
        else:
            entities = await self._farmer_repository.list(
                offset=query.offset,
                limit=query.limit,
                vlcc_id=query.vlcc_id,
                owner=query.owner
            )

        return [
            self._to_list_dto(entity)
            for entity in entities
        ]

    async def count(self, vlcc_id: UUID | None = None, owner: CurrentUser | None = None) -> int:
        return await self._farmer_repository.count(vlcc_id=vlcc_id, owner=owner)

    async def count_search(self, keyword: str, vlcc_id: UUID | None = None, owner: CurrentUser | None = None) -> int:
        return await self._farmer_repository.count_search(keyword=keyword, vlcc_id=vlcc_id, owner=owner)

    async def get_farmers_detail_for_sync(self, vlcc_id: UUID, owner: CurrentUser) -> list[SubUserProfileSyncDto]:
        rows = await self._farmer_repository.get_farmers_full_detail_by_vlcc_id(vlcc_id)
        return [
            self._to_farmer_full_detail_dto(
                row.FarmerModel,
                row.UserModel,
                row.AddressModel,
                row.BankAccountModel,
                owner,
                getattr(row, "VlccModel", None),
            )
            for row in rows
        ]

    async def get_full_detail(self, farmer_id: UUID, owner: CurrentUser | None = None) -> FarmerFullDetailDto | None:
        row = await self._farmer_repository.full_detail(farmer_id, owner)
        if row is None:
            return None
        return self._to_single_farmer_full_detail_dto(row, owner)

    async def get_full_detail_by_code(
        self,
        farmer_code: str,
        vlcc_id: UUID,
        owner: CurrentUser | None = None,
    ) -> FarmerFullDetailDto | None:
        row = await self._farmer_repository.get_full_detail_by_code(farmer_code, vlcc_id, owner)
        if row is None:
            return None
        return self._to_single_farmer_full_detail_dto(row, owner)

    def _to_single_farmer_full_detail_dto(self, row: Any, owner: CurrentUser | None = None) -> FarmerFullDetailDto:
        user: UserModel = row.UserModel
        farmer: FarmerModel = row.FarmerModel
        address: AddressModel = row.AddressModel
        bank_account: BankAccountModel = row.BankAccountModel
        vlcc: VlccModel = row.VlccModel
        vlcc_user = getattr(row, "VlccUser", None)
        if not owner:
            can_modify = False
        else:
            is_vlcc = owner.role_type == Role.VLCC
            farmer_enabled = getattr(vlcc, "farmer_enabled", False) if vlcc else False
            is_creator_or_center = (
                farmer.created_by == owner.id
                or (vlcc and vlcc.created_by == owner.id)
                or (vlcc and farmer.vlcc_id == vlcc.id)
            )
            can_modify = bool(is_vlcc and farmer_enabled and is_creator_or_center)

        return FarmerFullDetailDto(
            user=UserDto(
                id=user.id,
                name=user.name,
                email=user.email,
                mobile=user.mobile,
                role=Role.FARMER,
                is_active=user.is_active,
                created_by=user.created_by,
                is_locked=user.is_locked,
                created_at=user.created_at,
                profile_image=user.profile_url,
            ),
            farmer=FarmerDto(
                id=farmer.id,
                name= user.name,
                user_id=farmer.user_id,
                farmer_code=farmer.farmer_code,
                vlcc_id=farmer.vlcc_id,
                address_id=farmer.address_id,
                bank_account_id=farmer.bank_account_id,
                milk_type=farmer.milk_type,
                assigned_chart_rank=farmer.assigned_chart_rank,
                profile_image=user.profile_url,
                sms_enabled=farmer.sms_enabled,
                is_active=farmer.is_active,
                vlcc_name=vlcc.name if vlcc else None,
                can_modify=can_modify,
            ),
            vlcc=VlccForFarmerDto(
                id=vlcc.id,
                code=vlcc.vlcc_code,
                name=vlcc.name,
                email=vlcc_user.email if vlcc_user else None,
                mobile=vlcc_user.mobile if vlcc_user else None,
                profile_image=vlcc_user.profile_url if vlcc_user else None,
                uic_code=vlcc.uic_code,
            ) if vlcc and vlcc_user else None,
            address=AddressMapper.to_dto(address) if address else None,
            bank_account=BankAccountMapper.to_dto(bank_account) if bank_account else None,
        )

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        farmer: Farmer,
    ) -> FarmerListDto:
        return FarmerListDto(
            id=farmer.id,
            user_id=farmer.user_id,
            farmer_code=farmer.farmer_code,
            name=farmer.name or "",
            milk_type=farmer.milk_type,
            vlcc_id=farmer.vlcc_id,
            is_active=farmer.is_active,
            profile_image=farmer.profile_image,
            vlcc_name=farmer.vlcc_name if farmer.vlcc_name else "",
            assigned_chart_rank=farmer.assigned_chart_rank if farmer.assigned_chart_rank is not None else 1,
            can_modify=farmer.can_modify,
            mobile=farmer.mobile,
        )

    def _to_dto(self, farmer: Farmer) -> FarmerDto:
        return FarmerDto(
            id=farmer.id,
            user_id=farmer.user_id,
            farmer_code=farmer.farmer_code,
            name=farmer.name or "",
            vlcc_id=farmer.vlcc_id,
            address_id=farmer.address_id,
            bank_account_id=farmer.bank_account_id,
            milk_type=farmer.milk_type,
            assigned_chart_rank=farmer.assigned_chart_rank if farmer.assigned_chart_rank is not None else 1,
            profile_image=farmer.profile_image,
            sms_enabled=farmer.sms_enabled,
            is_active=farmer.is_active,
            vlcc_name=farmer.vlcc_name,
            can_modify=farmer.can_modify,
            mobile=farmer.mobile,
        )

    def _to_farmer_full_detail_dto(
        self,
        farmer: FarmerModel,
        user: UserModel,
        address: AddressModel,
        bank_account: BankAccountModel,
        owner: CurrentUser | None = None,
        vlcc: VlccModel | None = None,
    ) -> SubUserProfileSyncDto:
        if not owner:
            can_modify = False
        else:
            is_vlcc = owner.role_type == Role.VLCC
            farmer_enabled = getattr(vlcc, "farmer_enabled", False) if vlcc else False
            is_creator_or_center = (
                farmer.created_by == owner.id
                or (vlcc and vlcc.created_by == owner.id)
                or (vlcc and farmer.vlcc_id == vlcc.id)
            )
            can_modify = bool(is_vlcc and farmer_enabled and is_creator_or_center)

        rate_chart_val = farmer.assigned_chart_rank if farmer.assigned_chart_rank is not None else 1
        return SubUserProfileSyncDto(
            id=farmer.id,
            user_id=farmer.user_id,
            code=farmer.farmer_code,
            name=user.name,
            email=user.email,
            mobile=user.mobile,
            role=Role.FARMER,
            profile_image=user.profile_url,
            uic_code=None,
            milk_type=farmer.milk_type,
            assigned_chart_rank=rate_chart_val,
            can_modify=can_modify,
            address=AddressMapper.to_dto(address) if address else None,
            bank_account=BankAccountMapper.to_dto(bank_account) if bank_account else None,
        )