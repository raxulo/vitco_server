from app.modules.vlcc.domain.enums import VlccType
from app.modules.vlcc.application.command import PartialUpdateFullDetailVlcc
from app.api.v1.schemas.sync import SubUserProfileSyncDto
from app.modules.vlcc.domain.dto import VlccForMccDto
from app.modules.vlcc.domain.dto import VlccWithAllDetailsForMccDto
from app.middleware.authentication import CurrentUser
from app.modules.vlcc.domain.dto import VlccWithMccListDto
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from app.modules.vlcc.domain.exceptions import VlccConfigurationNotFoundException
from app.modules.common.milk_quality.application.command import UpdateMilkQualityConfigCommand
from app.modules.common.settings.application.command import UpdateSettingsCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.administration.application.command import UpdateUserCommand
from dataclasses import replace
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.vlcc.infrastructure.mapper import VlccMapper
from app.modules.administration.infrastructure.mapper import UserMapper
from app.modules.vlcc.application.command import CreateVlcc
from app.modules.common.milk_quality.application.command import CreateMilkQualityConfigCommand
from dataclasses import asdict
from app.modules.common.settings.application.dto import CreateSettingsCommand
import ipaddress
from app.modules.common.profile.application.command import CreatedProfile
from app.modules.common.profile.application.services import ProfileService

from app.modules.common.bank.infrastructure.mapper import BankAccountMapper
from app.modules.common.address.infrastructure.mapper import AddressMapper
from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.common.milk_quality.presentation.response import MilkQualityConfigResponse

from datetime import UTC, datetime
from uuid import UUID, uuid4
from email_validator import validate_email

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.administration.domain.enums import Role
from app.modules.administration.domain.entities import User
from app.modules.administration.domain.exceptions import (
    EmailAlreadyExistsException,
    MobileAlreadyExistsException,
    UserNotFoundException,
)
from app.modules.administration.infrastructure.repository import UserRepository
from app.modules.vlcc.domain.entities import Vlcc
from app.modules.vlcc.domain.exceptions import (
    VlccNotFoundException,
    VlccCodeAlreadyExistsException,
)
from app.modules.vlcc.infrastructure.repository import VlccRepository
from app.modules.vlcc.domain.dto import VlccDto, VlccListDto, VlccDetailDto
from app.modules.vlcc.application.command import (
    CreateVlccCommand,
    UpdateVlccCommand,
    DeleteVlccCommand,
    GetVlccQuery,
    ListVlccQuery,
    CreateFullDetailVlcc,
    UpdateFullDetailVlcc,
)
from app.modules.common.address.infrastructure.repository import AddressRepository
from app.modules.common.bank.infrastructure.repository import BankAccountRepository
from app.modules.common.settings.infrastructure.repository import SettingsRepository
from app.modules.common.milk_quality.infrastructure.repository import MilkQualityConfigRepository
from app.modules.common.address.domain.entities import Address
from app.modules.common.bank.domain.entities import BankAccount
from app.modules.common.settings.domain.entities import Settings
from app.modules.common.milk_quality.domain.entities import MilkQualityConfig
from app.core.clock import now_naive_ist


class VlccHandler:

    __slots__ = (
        "_database",
        "_user_repository",
        "_vlcc_repository",
        "_settings_repository",
        "_milk_quality_config_repository",
        "_password",
        "_profile",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        user_repository: UserRepository,
        vlcc_repository: VlccRepository,
        settings_repository: SettingsRepository,
        milk_quality_config_repository: MilkQualityConfigRepository,
        password: PasswordService,
        profile_service: ProfileService
    ) -> None:
        self._database = database
        self._user_repository = user_repository
        self._vlcc_repository = vlcc_repository
        self._settings_repository = settings_repository
        self._milk_quality_config_repository = milk_quality_config_repository
        self._password = password
        self._profile = profile_service

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateVlccCommand,
        owner: CurrentUser | None = None,
    ) -> VlccDto:
        self._validate(command)

        await self._ensure_code_available(command.vlcc_code, owner)
        await self._ensure_email_available(command.email)
        if command.mobile and command.mobile.strip():
            await self._ensure_mobile_available(command.mobile.strip())

        async with self._database.transaction():
            user = self._build_user(command)
            await self._profile.create(user_data=user, role=Role.VLCC)
            vlcc = self._build_vlcc(command, user.id)
            await self._vlcc_repository.create(vlcc, owner)

        return self._to_dto(vlcc)

    async def create_only_vlcc(
        self,
        command: CreateVlccCommand,
        user_id: UUID,
        owner: CurrentUser | None = None,
    ):
        self._validate(command)

        await self._ensure_code_available(command.vlcc_code, owner)
        vlcc = self._build_vlcc(command, user_id)
        await self._vlcc_repository.create(vlcc, owner)

        return self._to_dto(vlcc)

    # =========================================================
    # UPDATE
    # =========================================================

    # async def update(
    #     self,
    #     command: UpdateVlccCommand,
    # ) -> VlccDto:
    #     self._validate(command)

    #     async with self._database.transaction():
    #         vlcc = await self._vlcc_repository.get_by_id(command.id)
    #         if vlcc is None:
    #             raise VlccNotFoundException()

    #         user = await self._user_repository.get_by_id(vlcc.user_id)
    #         if user is None:
    #             raise UserNotFoundException()

    #         self._update_user(user, command)
    #         self._update_vlcc(vlcc, command)

    #         await self._user_repository.update(user)
    #         await self._vlcc_repository.update(vlcc)

    #     return self._to_dto(vlcc)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteVlccCommand,
    ) -> None:
        async with self._database.transaction():
            vlcc = await self._vlcc_repository.get_by_id(command.id, command.owner)
            if vlcc is None:
                raise VlccNotFoundException()
            self._ensure_mcc_can_modify(vlcc, command.owner)

            user = await self._user_repository.get_by_id(vlcc.user_id)
            if user is None:
                raise UserNotFoundException()

            now = now_naive_ist()

            # Soft delete user
            user.is_active = False
            user.is_deleted = True
            user.deleted_at = now
            user.deleted_by = command.deleted_by

            # Soft delete vlcc
            vlcc.is_active = False
            vlcc.is_deleted = True
            vlcc.deleted_at = now
            vlcc.deleted_by = command.deleted_by

            # A deleted user's profile image is removed (file + media row)
            await self._profile.delete_profile_image(user.id)
            user.profile_image = None

            await self._user_repository.update(user)
            await self._vlcc_repository.update(vlcc, command.owner)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetVlccQuery,
    ) -> VlccDto:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        vlcc = await self._vlcc_repository.get_by_id(query.id, query.owner)
        if vlcc is None:
            raise VlccNotFoundException()

        return self._to_dto(vlcc)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListVlccQuery,
    ) -> list[VlccListDto]:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        if query.keyword:
            entities = await self._vlcc_repository.search(
                keyword=query.keyword,
                offset=query.offset,
                limit=query.size,
                owner=query.owner,
                manager=query.manager,
            )
        else:
            entities = await self._vlcc_repository.list(
                offset=query.offset,
                limit=query.size,
                owner=query.owner,
                manager=query.manager,
            )

        return [
            self._to_list_dto(entity)
            for entity in entities
        ]

    async def count(
        self,
        keyword: str | None = None,
        owner: CurrentUser | None = None,
        manager: CurrentUser | None = None,
    ) -> int:
        if owner is None:
            raise PermissionError("Owner context is required")
        if keyword:
            return await self._vlcc_repository.count_search(keyword, owner, manager=manager)
        return await self._vlcc_repository.count(owner, manager=manager)

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        vlcc: Vlcc,
    ) -> VlccListDto:
        return VlccListDto(
            id=vlcc.id,
            user_id=vlcc.user_id,
            vlcc_code=vlcc.vlcc_code,
            uic_code=vlcc.uic_code,
            name=vlcc.name,
            entry_mode=vlcc.entry_mode,
            route_code=vlcc.route_code,
            is_active=vlcc.is_active,
            assigned_chart_rank=vlcc.assigned_chart_rank,
            owner_name=vlcc.owner_name,
            profile_image=vlcc.profile_image,
            analyzer_collection_mode=vlcc.analyzer_collection_mode,
            weight_collection_mode=vlcc.weight_collection_mode,
            can_modify=vlcc.can_modify,
            city=vlcc.city,
            vlcc_type=vlcc.vlcc_type,
        )

    def _to_dto(
        self,
        vlcc: Vlcc,
    ) -> VlccDto:
        return VlccDto(
            id=vlcc.id,
            user_id=vlcc.user_id,
            uic_code=vlcc.uic_code,
            vlcc_code=vlcc.vlcc_code,
            name=vlcc.name,
            contact_person=vlcc.contact_person,
            address_id=vlcc.address_id,
            bank_account_id=vlcc.bank_account_id,
            milk_quality_config_id=vlcc.milk_quality_config_id,
            settings_id=vlcc.settings_id,
            profile_image=vlcc.profile_image,
            entry_mode=vlcc.entry_mode,
            route_code=vlcc.route_code,
            route_name=vlcc.route_name,
            soc_percentage=vlcc.soc_percentage,
            farmer_enabled=vlcc.farmer_enabled,
            is_active=vlcc.is_active,
            assigned_chart_rank=vlcc.assigned_chart_rank,
            owner_name=vlcc.owner_name,
            can_modify=vlcc.can_modify,
            city=vlcc.city,
        )

    def _build_user(self, command: CreateVlccCommand) -> User:
        from app.modules.vlcc.domain.enums import VlccType
        now = now_naive_ist()
        user_role = Role.VLCC_FARMER if getattr(command, "vlcc_type", None) == VlccType.VLCC_FARMER_TYPE else Role.VLCC
        return User(
            id=uuid4(),
            name=command.name,
            email=command.email.lower(),
            mobile=command.mobile,
            password_hash=self._password.hash(command.password),
            role=user_role,
            created_by=command.created_by,
            is_active=True,
            is_locked=False,
            created_at=now,
            updated_at=now,
            profile_image=command.profile_image
        )

    def _build_vlcc(
        self,
        command: CreateVlccCommand,
        user_id: UUID, 
        address_id: UUID | None = None, 
        bank_account_id: UUID | None = None, 
        settings_id: UUID | None = None,
        milk_quality_config_id: UUID | None = None, 
    ) -> CreateVlcc:
        return CreateVlcc(
            user_id=user_id,
            uic_code=command.uic_code.strip(),
            vlcc_code=command.vlcc_code.strip(),
            name=command.name.strip(),
            contact_person=command.contact_person.strip() if command.contact_person else None,
            address_id=address_id,
            bank_account_id=bank_account_id,
            milk_quality_config_id=milk_quality_config_id,
            settings_id=settings_id,
            entry_mode=command.entry_mode,
            route_code=str(command.route_code or 0) if command.route_code else None,
            soc_percentage=command.soc_percentage,
            farmer_enabled=command.farmer_enabled,
            is_active=True,
            assigned_chart_rank=command.assigned_chart_rank,
            created_by=command.created_by,
            vlcc_type=command.vlcc_type,
        )

    def _validate(
        self,
        command: CreateVlccCommand | UpdateVlccCommand,
    ) -> None:
        if len(command.name.strip()) < 3:
            raise ValidationException("Invalid VLCC Name")

        # Email format validation

    @staticmethod
    def ensure_can_create(owner: CurrentUser | None) -> None:
        """Super Admin, Admin, Sub Admin and MCC create VLCCs (a VLCC never creates another VLCC)."""
        if owner is None or owner.role_type in (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC):
            return
        if owner.role_type == Role.VLCC:
            raise PermissionError("A VLCC cannot create another VLCC.")
        raise PermissionError("You are not allowed to create a VLCC.")

    @staticmethod
    def _ensure_mcc_can_modify(vlcc, owner: CurrentUser | None) -> None:
        """An MCC sees its creator's VLCCs (its suppliers) but modifies only the VLCCs it created."""
        if vlcc is not None and owner is not None and owner.role_type == Role.MCC and not vlcc.can_modify:
            raise PermissionError("This VLCC can be viewed and used, but not modified.")

    async def _ensure_code_available(
        self,
        code: str,
        owner: CurrentUser | None = None,
        exclude_id: UUID | None = None,
    ) -> None:
        """The code must be free in the owner's line (itself, above, below)."""
        if owner is not None and await self._vlcc_repository.exists_code(code, owner, exclude_id=exclude_id):
            raise VlccCodeAlreadyExistsException(f"VLCC code {code.strip()} already exists.")

    async def _ensure_email_available(self, email: str) -> None:
        if await self._user_repository.exists_email(email):
            raise EmailAlreadyExistsException(f"Email {email.strip()} already exists.")

    async def _ensure_mobile_available(self, mobile: str, exclude_user_id: UUID | None = None) -> None:
        if await self._user_repository.exists_mobile(mobile, exclude_user_id=exclude_user_id):
            raise MobileAlreadyExistsException(f"Mobile number {mobile.strip()} is already registered.")

    def _update_user(
        self,
        user: User,
        command: UpdateVlccCommand,
    ) -> None:
        user.name = command.name.strip()
        user.email = command.email.lower()

        if command.password:
            user.password_hash = self._password.hash(command.password)

        user.updated_at = now_naive_ist()
        user.updated_by = command.updated_by

    def _updated_vlcc(
        self,
        vlcc: Vlcc,
        command: UpdateVlccCommand, user_id: UUID,  address_id:UUID=None,
        bank_account_id: UUID=None, milk_quality_config_id: UUID=None,
        settings_id: UUID=None,
    ) -> Vlcc:
        return replace(vlcc, 
            user_id=user_id,
            name = command.name.strip(),
            uic_code=command.uic_code,
            vlcc_code=command.vlcc_code,
            contact_person = command.contact_person.strip() if command.contact_person else None,
            address_id=address_id,
            bank_account_id=bank_account_id,
            milk_quality_config_id=milk_quality_config_id,
            settings_id=settings_id,
            entry_mode=command.entry_mode,
            route_code=command.route_code if command.route_code else None,
            soc_percentage=command.soc_percentage,
            farmer_enabled=command.farmer_enabled,
            is_active=command.is_active,
            assigned_chart_rank=command.assigned_chart_rank,
            vlcc_type=command.vlcc_type,
            updated_at=now_naive_ist(),
        )

    async def full_create(
        self,
        command: CreateFullDetailVlcc,
        owner: CurrentUser,
    ) -> bool:
        self.ensure_can_create(owner)
        self._validate(command.vlcc)
        await self._ensure_code_available(command.vlcc.vlcc_code, owner)

        settings_1 = self._build_setting(command=command.setting)
        profile = None
        milk_quality = None
        settings = None

        async with self._database.transaction():
            from app.modules.vlcc.domain.enums import VlccType
            target_role = (
                Role.VLCC_FARMER
                if getattr(command.vlcc, "vlcc_type", None) == VlccType.VLCC_FARMER_TYPE
                or getattr(command.user, "role", None) == Role.VLCC_FARMER
                else Role.VLCC
            )
            profile = await self._profile.create(
                user_data=command.user,
                address_data=command.address,
                bank_data=command.bank_account,
                role=target_role,
            )
            settings = await self._settings_repository.create(settings=settings_1)
            milk_quality = self._build_milk_quality_config(command=command.milk_quality_config, user_id=profile.user.id)
            await self._milk_quality_config_repository.create(milk_quality)
            await self._database.session.flush()
            vlcc = self._build_vlcc(command=command.vlcc,user_id=profile.user.id, address_id=profile.address.id if profile.address else None, bank_account_id=profile.bank_account.id if profile.bank_account else None, settings_id=settings.id if settings else None, milk_quality_config_id=milk_quality.id if milk_quality else None)
            await self._vlcc_repository.create(vlcc, owner)

            if command.device_item_versions:
                from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel
                for item in command.device_item_versions:
                    dev_version = DeviceItemVersionModel(
                        id=uuid4(),
                        device_type=2, # 2 for VLCC
                        device_id=profile.user.id,
                        item_name=item.item_name,
                        version=item.version,
                        created_at=now_naive_ist(),
                        updated_at=now_naive_ist(),
                    )
                    self._database.session.add(dev_version)

        return True

    def _build_setting(self, command: CreateSettingsCommand) -> Settings:
        return Settings(**asdict(command), id=uuid4())

    def _build_milk_quality_config(self, command: CreateMilkQualityConfigCommand, user_id:UUID)-> MilkQualityConfig:
        ff = dict(**command.model_dump())
        ff.pop('id',None)
        ff.pop('user_id',None)
        return MilkQualityConfig(**ff, id=uuid4(), user_id=user_id)

    async def update(
        self,
        command: UpdateFullDetailVlcc,
        owner: CurrentUser,
    ) -> bool:

        self._validate(command.vlcc)
        # Only a changed code is checked: an unchanged code never clashes with itself
        current = await self._vlcc_repository.get_by_id(command.vlcc.id, owner)
        self._ensure_mcc_can_modify(current, owner)
        if current is None or (current.vlcc_code or "").strip() != (command.vlcc.vlcc_code or "").strip():
            await self._ensure_code_available(command.vlcc.vlcc_code, owner, exclude_id=command.vlcc.id)

        async with self._database.transaction():

            # ---------------------------------------------
            # VLCC relation IDs
            # ---------------------------------------------

            vlcc_relation = await self._vlcc_repository.get_relations(command.vlcc.id)

            if vlcc_relation is None:
                raise VlccNotFoundException()

            # ---------------------------------------------
            # USER
            # ---------------------------------------------

            from app.modules.vlcc.domain.enums import VlccType
            target_role = (
                Role.VLCC_FARMER
                if getattr(command.vlcc, "vlcc_type", None) == VlccType.VLCC_FARMER_TYPE
                or getattr(command.user, "role", None) == Role.VLCC_FARMER
                else Role.VLCC
            )
            await self._profile.update(
                user_data=UpdateUserCommand(
                    id=vlcc_relation.user_id,
                    name=command.user.name,
                    email=command.user.email,
                    mobile=command.user.mobile,
                    role=target_role,
                    is_active=command.user.is_active,
                    password_hash=command.user.password_hash,
                    updated_by=command.updated_by,
                    profile_image=command.user.profile_image,
                )
            )

            # ---------------------------------------------
            # ADDRESS
            # ---------------------------------------------

            address_id = vlcc_relation.address_id

            if command.address:

                address_data = asdict(command.address)

                if address_id:
                    await self._profile.address_update(
                        UpdateAddressCommand(
                            id=address_id,
                            **address_data,
                        )
                    )

                else:
                    address = await self._profile.create_address(
                        user_id=vlcc_relation.user_id,
                        address_data=CreateAddressCommand(
                            **address_data,
                        ),
                    )

                    address_id = address.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # BANK ACCOUNT
            # ---------------------------------------------

            bank_account_id = vlcc_relation.bank_account_id

            if command.bank_account:

                bank_data = asdict(command.bank_account)

                if bank_account_id:
                    await self._profile.bank_update(
                        UpdateBankAccountCommand(
                            id=bank_account_id,
                            **bank_data,
                        )
                    )

                else:
                    bank = await self._profile.create_bank_account(
                        user_id=vlcc_relation.user_id,
                        bank_data=CreateBankAccountCommand(
                            **bank_data,
                        ),
                    )

                    bank_account_id = bank.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # SETTINGS
            # ---------------------------------------------

            settings_id = vlcc_relation.settings_id

            if command.setting:

                if not settings_id:
                    setting = await self._settings_repository.create(
                        Settings(
                            id=uuid4(),
                            **asdict(command.setting),
                        )
                    )

                    settings_id = setting.id
                    await self._database.session.flush()

                else:
                    await self._settings_repository.update(
                        Settings(
                            id=settings_id,
                            **asdict(command.setting),
                        )
                    )

            # ---------------------------------------------
            # MILK QUALITY CONFIG
            # ---------------------------------------------

            quality_id = vlcc_relation.milk_quality_config_id



            if command.milk_quality_config:

                if not quality_id:
                    milk_quality_data = command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"])
                    milk_data = MilkQualityConfig(
                            id=uuid4(),
                            user_id=vlcc_relation.user_id,
                            **milk_quality_data,
                        )
                    await self._milk_quality_config_repository.create(milk_data)
                    quality_id = milk_data.id
                    await self._database.session.flush()

                else:
                    await self._milk_quality_config_repository.update(
                        MilkQualityConfig(
                            id=quality_id,
                            user_id=vlcc_relation.user_id,
                            **command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"]),
                        )
                    )

            # ---------------------------------------------
            # VLCC
            # ---------------------------------------------

            vlcc = await self._vlcc_repository.get_by_id(vlcc_relation.id, owner)

            if vlcc is None:
                raise VlccNotFoundException()

            await self._vlcc_repository.update(
                self._updated_vlcc(
                    vlcc=vlcc,
                    command=command.vlcc,
                    user_id=vlcc_relation.user_id,
                    address_id=address_id,
                    bank_account_id=bank_account_id,
                    settings_id=settings_id,
                    milk_quality_config_id=quality_id,
                ),
                owner,
            )

            await self._database.session.flush()

            if command.device_item_versions is not None:
                from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel
                from sqlalchemy import delete
                
                stmt = delete(DeviceItemVersionModel).where(DeviceItemVersionModel.device_id == vlcc_relation.user_id)
                await self._database.session.execute(stmt)
                
                for item in command.device_item_versions:
                    dev_version = DeviceItemVersionModel(
                        id=uuid4(),
                        device_type=2, # 2 for VLCC
                        device_id=vlcc_relation.user_id,
                        item_name=item.item_name,
                        version=item.version,
                        created_at=now_naive_ist(),
                        updated_at=now_naive_ist(),
                    )
                    self._database.session.add(dev_version)

        return True

    async def get_full_detail(
        self,
        query: GetVlccQuery,
    ) -> VlccDetailDto:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        vlcc = await self._vlcc_repository.get_by_id(query.id, query.owner)
        if vlcc is None:
            raise VlccNotFoundException()

        profile = await self._profile.get_profile(user_id=vlcc.user_id)
        if profile is None:
            raise UserNotFoundException()

        setting = await self._settings_repository.get_by_id(vlcc.settings_id) if vlcc.settings_id else None
        milk_quality_config = await self._milk_quality_config_repository.get_by_id(vlcc.milk_quality_config_id) if vlcc.milk_quality_config_id else None

        return self._to_detail_dto(vlcc, profile.user, profile.address, profile.bank_account, setting, milk_quality_config)
    
    async def validate_code(self, code: str, owner: CurrentUser) -> bool:
        """Live form check: same rule as create (code free in the owner's line)."""
        return not await self._vlcc_repository.exists_code(code, owner)

    async def validate_uic_code(self, code: str, owner: CurrentUser) -> bool:
        vlcc = await self._vlcc_repository.get_by_uic_code(code, owner=owner)
        return True if not vlcc else False

    def _to_detail_dto(
        self, 
        vlcc: Vlcc, 
        user: User, 
        address: Address | None, 
        bank_account: BankAccount | None,
        setting: Settings | None = None,
        milk_quality_config: MilkQualityConfig | None = None,
    ) -> VlccDetailDto:
        return VlccDetailDto(
            user=UserMapper.entity_to_dto(user) if user else None,
            vlcc=VlccMapper.to_dto(vlcc) if vlcc else None,
            address=AddressMapper.to_dto(address) if address else None,
            bank_account=BankAccountMapper.to_dto(bank_account) if bank_account else None,
            setting=SettingsResponse.model_validate(setting) if setting else None,
            milk_quality_config=MilkQualityConfigResponse.model_validate(milk_quality_config) if milk_quality_config else None,
        )

    async def get_vlccs_by_mcc(self, mcc_id: UUID, owner: CurrentUser):
        result = await self._vlcc_repository.get_vlccs_half_detail_by_mcc(mcc_id, owner)

        return [VlccWithMccListDto(
            vlcc_id=row.VlccModel.id,
            mcc_id=mcc_id,
            vlcc_code=row.VlccModel.vlcc_code,
            vlcc_name=row.VlccModel.name,
            assigned_chart_rank=row.VlccModel.assigned_chart_rank,
            uic_code=row.VlccModel.uic_code,
            route_code=row.VlccModel.route_code,
            mobile=row.UserModel.mobile if row.UserModel else None,
            owner_name=row.owner_name,
        ) for row in result]

    async def get_vlccs_with_details_by_mcc(
        self,
        mcc_id: UUID,
        owner: CurrentUser | None = None,
    ) -> list[SubUserProfileSyncDto]:

        rows = await self._vlcc_repository.get_vlccs_half_detail_by_mcc(mcc_id, owner)

        owner_id = owner.id if owner is not None else None

        return [
            SubUserProfileSyncDto(
                id=row.VlccModel.id,
                user_id=row.VlccModel.user_id,
                code=row.VlccModel.vlcc_code,
                name=row.VlccModel.name,
                email=row.UserModel.email if row.UserModel else "",
                mobile=row.UserModel.mobile if row.UserModel else None,
                role=Role.VLCC,
                profile_image=row.UserModel.profile_url if row.UserModel else None,
                uic_code=row.VlccModel.uic_code,
                milk_type=None,
                assigned_chart_rank=row.VlccModel.assigned_chart_rank or 1,
                can_modify=(owner_id is not None and row.VlccModel.created_by == owner_id),
                address=AddressMapper.to_dto(row.AddressModel) if row.AddressModel else None,
                bank_account=BankAccountMapper.to_dto(row.BankAccountModel) if row.BankAccountModel else None,
            )
            for row in rows
        ]

    async def partial_update(
            self,
            command: PartialUpdateFullDetailVlcc,
            owner: CurrentUser,
        ) -> bool:

            async with self._database.transaction():

                # ---------------------------------------------
                # VLCC relation IDs
                # ---------------------------------------------

                vlcc_relation = await self._vlcc_repository.get_relations(owner.own_id)

                if vlcc_relation is None:
                    raise VlccNotFoundException()

                # ---------------------------------------------
                # USER
                # ---------------------------------------------
                if command.user:
                    await self._profile.update(
                        user_data=UpdateUserCommand(
                            id=vlcc_relation.user_id,
                            name=command.user.name,
                            email=command.user.email,
                            role=Role.VLCC,
                            password_hash=None,
                            mobile=command.user.mobile,
                            updated_by=command.updated_by,
                        )
                    )

                # ---------------------------------------------
                # ADDRESS
                # ---------------------------------------------

                address_id = vlcc_relation.address_id

                if command.address:

                    address_data = asdict(command.address)

                    if address_id:
                        await self._profile.address_update(
                            UpdateAddressCommand(
                                id=address_id,
                                **address_data,
                            )
                        )

                    else:
                        address = await self._profile.create_address(
                            user_id=vlcc_relation.user_id,
                            address_data=CreateAddressCommand(
                                **address_data,
                            ),
                        )

                        address_id = address.id
                        await self._database.session.flush()

                # ---------------------------------------------
                # BANK ACCOUNT
                # ---------------------------------------------

                bank_account_id = vlcc_relation.bank_account_id

                if command.bank_account:

                    bank_data = asdict(command.bank_account)

                    if bank_account_id:
                        await self._profile.bank_update(
                            UpdateBankAccountCommand(
                                id=bank_account_id,
                                **bank_data,
                            )
                        )

                    else:
                        bank = await self._profile.create_bank_account(
                            user_id=vlcc_relation.user_id,
                            bank_data=CreateBankAccountCommand(
                                **bank_data,
                            ),
                        )

                        bank_account_id = bank.id
                        await self._database.session.flush()

                # ---------------------------------------------
                # SETTINGS
                # ---------------------------------------------

                settings_id = vlcc_relation.settings_id

                if command.setting:

                    if not settings_id:
                        setting = await self._settings_repository.create(
                            Settings(
                                id=uuid4(),
                                **asdict(command.setting),
                            )
                        )

                        settings_id = setting.id
                        await self._database.session.flush()

                    else:
                        await self._settings_repository.update(
                            Settings(
                                id=settings_id,
                                **asdict(command.setting),
                            )
                        )

                # ---------------------------------------------
                # MILK QUALITY CONFIG
                # ---------------------------------------------

                quality_id = vlcc_relation.milk_quality_config_id



                if command.milk_quality_config:

                    if not quality_id:
                        milk_quality_data = command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"])
                        milk_data = MilkQualityConfig(
                                id=uuid4(),
                                user_id=vlcc_relation.user_id,
                                **milk_quality_data,
                            )
                        await self._milk_quality_config_repository.create(milk_data)
                        quality_id = milk_data.id
                        await self._database.session.flush()

                    else:
                        await self._milk_quality_config_repository.update(
                            MilkQualityConfig(
                                id=quality_id,
                                user_id=vlcc_relation.user_id,
                                **command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"]),
                            )
                        )

                # ---------------------------------------------
                # VLCC
                # ---------------------------------------------

                vlcc = await self._vlcc_repository.get_by_id(vlcc_relation.id, owner)

                if vlcc is None:
                    raise VlccNotFoundException()
                vlcc_command = asdict(vlcc)
                
                vlcc_keys = set(asdict(UpdateVlccCommand(id=vlcc.id, name="", updated_by=uuid4(), email="[EMAIL_ADDRESS]")).keys())
                vlcc_command = {key: value for key, value in vlcc_command.items() if key in vlcc_keys}
                await self._vlcc_repository.update(
                    self._updated_vlcc(
                        vlcc=vlcc,
                        command=UpdateVlccCommand(
                            **vlcc_command,
                            updated_by=owner.id,
                            email=None,
                        ),
                        user_id=vlcc_relation.user_id,
                        address_id=address_id,
                        bank_account_id=bank_account_id,
                        settings_id=settings_id,
                        milk_quality_config_id=quality_id,
                    ),
                    owner,
                )

                await self._database.session.flush()

                if command.device_item_versions is not None:
                    from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel
                    from sqlalchemy import delete
                    
                    stmt = delete(DeviceItemVersionModel).where(DeviceItemVersionModel.device_id == vlcc_relation.user_id)
                    await self._database.session.execute(stmt)
                    
                    for item in command.device_item_versions:
                        dev_version = DeviceItemVersionModel(
                            id=uuid4(),
                            device_type=2, # 2 for VLCC
                            device_id=vlcc_relation.user_id,
                            item_name=item.item_name,
                            version=item.version,
                            created_at=now_naive_ist(),
                            updated_at=now_naive_ist(),
                        )
                        self._database.session.add(dev_version)

            return True
