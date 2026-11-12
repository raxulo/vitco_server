from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.core.exceptions.base import ValidateError
from app.modules.mcc.application.command import UpdateFullDetailMcc
from app.modules.common.bank.infrastructure.mapper import BankAccountMapper
from app.modules.common.address.infrastructure.mapper import AddressMapper
from app.modules.mcc.application.command import CreateFullDetailMcc
from app.modules.common.profile.application.services import ProfileService
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.common.address.application.command import CreateAddressCommand, UpdateAddressCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand, UpdateBankAccountCommand
from app.modules.common.settings.application.command import UpdateSettingsCommand
from app.modules.mcc.domain.entities import MccRelations
from dataclasses import asdict, replace, is_dataclass
from app.modules.common.bank.infrastructure.repository import BankAccountRepository
from app.modules.common.address.infrastructure.repository import AddressRepository
from app.modules.common.settings.infrastructure.repository import SettingsRepository
from app.modules.common.milk_quality.infrastructure.repository import MilkQualityConfigRepository
from app.modules.common.settings.domain.entities import Settings
from app.modules.common.milk_quality.domain.entities import MilkQualityConfig
from app.modules.mcc.domain.dto import MccDetailDto
from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.common.milk_quality.presentation.response import MilkQualityConfigResponse
from app.modules.common.bank.domain.exceptions import BankAccountNotFoundException
from app.modules.common.address.domain.exceptions import AddressNotFoundException
from app.modules.common.address.domain.entities import Address
from app.modules.common.bank.domain.entities import BankAccount
from app.modules.common.fixedrate_config.infrastructure.repository import FixedRateConfigRepository
from app.modules.common.fixedrate_config.domain.entities import FixedRateConfig
from app.modules.common.fixedrate_config.presentation.response import FixedRateConfigResponse
from app.modules.administration.application.command import CreateUserCommand

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
from app.modules.mcc.domain.entities import Mcc
from app.modules.mcc.domain.exceptions import (
    MccNotFoundException,
    MccCodeAlreadyExistsException,
)
from app.modules.mcc.infrastructure.repository import MccRepository
from app.modules.mcc.domain.dto import MccDto, MccListDto
from app.modules.mcc.application.command import (
    CreateMccCommand,
    UpdateMccCommand,
    DeleteMccCommand,
    GetMccQuery,
    ListMccQuery,
    PartialUpdateFullDetailMcc,
)

class MccHandler:

    __slots__ = (
        "_database",
        "_user_repository",
        "_mcc_repository",
        "_address_repository",
        "_bank_account_repository",
        "_settings_repository",
        "_milk_quality_config_repository",
        "_fixed_rate_config_repository",
        "_password",
        "_profile",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        user_repository: UserRepository,
        address_repository: AddressRepository,
        bank_account_repository: BankAccountRepository,
        mcc_repository: MccRepository,
        settings_repository: SettingsRepository,
        milk_quality_config_repository: MilkQualityConfigRepository,
        fixed_rate_config_repository: FixedRateConfigRepository,
        password: PasswordService,
        profile_service: ProfileService,
    ) -> None:
        self._database = database
        self._user_repository = user_repository
        self._address_repository = address_repository
        self._bank_account_repository = bank_account_repository
        self._mcc_repository = mcc_repository
        self._settings_repository = settings_repository
        self._milk_quality_config_repository = milk_quality_config_repository
        self._fixed_rate_config_repository = fixed_rate_config_repository
        self._password = password
        self._profile = profile_service

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateMccCommand,
        address: str | None = None,
        bank_name: str | None = None,
        account_holder_name: str | None = None,
        account_number: str | None = None,
        ifsc_code: str | None = None,
        owner: CurrentUser | None = None
    ) -> MccDto:
        self._validate(command)

        await self._ensure_code_available(command.code, owner)
        await self._ensure_email_available(command.email)
        if command.mobile and command.mobile.strip():
            await self._ensure_mobile_available(command.mobile.strip())

        now = now_naive_ist()
        user_id = uuid4()
        address_id = None
        bank_account_id = None

        async with self._database.transaction():
            user = self._build_user(user_id,command,now,user_id)
            await self._user_repository.create(user)
            await self._database.session.flush()

            if address:
                address_id = uuid4()
                address_entity = Address(
                    id=address_id,
                    user_id=user_id,
                    line=address,
                    state=None,
                    city=None,
                    pincode=None,
                    created_at=now,
                    updated_at=now,
                )
                await self._address_repository.create(address_entity)

            if bank_name or account_holder_name or account_number or ifsc_code:
                bank_account_id = uuid4()
                bank_account_entity = BankAccount(
                    id=bank_account_id,
                    user_id=user_id,
                    account_holder=account_holder_name or command.name,
                    bank_name=bank_name,
                    account_number=account_number,
                    ifsc_code=ifsc_code,
                    created_at=now,
                    updated_at=now,
                )
                await self._bank_account_repository.create(bank_account_entity)

            mcc = self._build_mcc(command, user_id, address_id, bank_account_id)
            await self._mcc_repository.create(mcc, owner)


        return self._to_dto(mcc)


    async def full_create(
        self,
        command: CreateFullDetailMcc,
        owner: CurrentUser
    ) -> MccDetailDto:
        now = now_naive_ist()
        self.ensure_can_create(owner)
        self._password_validate(password=command.mcc.password)

        # Email / mobile uniqueness is enforced by ProfileService.create with a specific message
        await self._ensure_code_available(command.mcc.code, owner)


        async with self._database.transaction():
            user_cmd = CreateUserCommand(
                name=command.mcc.name,
                email=command.mcc.email,
                mobile=command.mcc.mobile,
                password_hash=command.mcc.password,
                role=Role.MCC,
                is_active=True,
                created_by=command.created_by,
                profile_image=command.mcc.profile_image
            )
            profile = await self._profile.create(
                user_data=user_cmd,
                address_data=command.address,
                bank_data=command.bank_account,
                role=Role.MCC
            )
            user_id = profile.user.id
            address_id = profile.address.id if profile.address else None
            bank_id = profile.bank_account.id if profile.bank_account else None

            settings_id = (uuid4() if command.setting else None)
            milk_quality_config_id = (uuid4() if command.milk_quality_config else None)
            fixed_rate_id = (uuid4() if command.fixed_rate_config else None)

            mcc = self._build_mcc(
                command.mcc,
                user_id,
                address_id,
                bank_id,
                now,
                settings_id=settings_id,
                milk_quality_config_id=milk_quality_config_id,
                rate_config_id=fixed_rate_id,
            )

            settings = None
            if settings_id:
                settings = Settings(
                    id=settings_id,
                    analyzer_type=command.setting.analyzer_type,
                    analyzer_collection_mode=command.setting.analyzer_collection_mode,
                    weight_unit=command.setting.weight_unit,
                    weight_collection_mode=command.setting.weight_collection_mode,
                    auto_tare_enabled=command.setting.auto_tare_enabled,
                    morning_collection_start=command.setting.morning_collection_start,
                    morning_collection_end=command.setting.morning_collection_end,
                    evening_collection_start=command.setting.evening_collection_start,
                    evening_collection_end=command.setting.evening_collection_end,
                    receipt_size=command.setting.receipt_size,
                    printer_type=command.setting.printer_type,
                    printer_enabled=command.setting.printer_enabled,
                    cattle_type=command.setting.cattle_type,
                    max_rate_chart_count=command.setting.max_rate_chart_count,
                    settings_edit_enabled=command.setting.settings_edit_enabled,
                    rate_chart_edit_enabled=command.setting.rate_chart_edit_enabled,
                    master_enabled=getattr(command.setting, "master_enabled", False) or False,
                )
                await self._settings_repository.create(settings)

            milk_quality = None
            if milk_quality_config_id:
                milk_quality = MilkQualityConfig(
                    id=milk_quality_config_id,
                    user_id=user_id,
                    cow_min_fat=command.milk_quality_config.cow_min_fat,
                    cow_max_fat=command.milk_quality_config.cow_max_fat,
                    cow_min_snf=command.milk_quality_config.cow_min_snf,
                    cow_max_snf=command.milk_quality_config.cow_max_snf,
                    buffalo_min_fat=command.milk_quality_config.buffalo_min_fat,
                    buffalo_max_fat=command.milk_quality_config.buffalo_max_fat,
                    buffalo_min_snf=command.milk_quality_config.buffalo_min_snf,
                    buffalo_max_snf=command.milk_quality_config.buffalo_max_snf,
                )
                await self._milk_quality_config_repository.create(milk_quality)

            fixed_rate = None
            if fixed_rate_id:
                fixed_rate = FixedRateConfig(
                    id=fixed_rate_id,
                    user_id=user_id,
                    fixed_rate=command.fixed_rate_config.fixed_rate,
                    less_detection=command.fixed_rate_config.less_detection,
                    high_detection=command.fixed_rate_config.high_detection,
                    min_fat=command.fixed_rate_config.min_fat,
                    max_fat=command.fixed_rate_config.max_fat,
                    min_snf=command.fixed_rate_config.min_snf,
                    max_snf=command.fixed_rate_config.max_snf,
                )
                await self._fixed_rate_config_repository.create(fixed_rate)

            await self._mcc_repository.create(mcc, owner)

            if command.device_item_versions:
                from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel
                for item in command.device_item_versions:
                    dev_version = DeviceItemVersionModel(
                        id=uuid4(),
                        device_type=1, # 1 for MCC
                        device_id=user_id,
                        item_name=item.item_name,
                        version=item.version,
                        created_at=now,
                        updated_at=now,
                    )
                    self._database.session.add(dev_version)

        return self._to_detail_dto(mcc, profile.user, profile.address, profile.bank_account, settings, milk_quality, fixed_rate)

    # =========================================================
    # UPDATE
    # =========================================================

    async def full_update(
        self,
        command: UpdateFullDetailMcc,
        owner: CurrentUser,
    ) -> bool:
        self._validate(command.mcc)
        # Only a changed code is checked: an unchanged code never clashes with itself
        current = await self._mcc_repository.get_by_id(command.mcc.id, owner)
        if current is None or (current.code or "").strip() != (command.mcc.code or "").strip():
            await self._ensure_code_available(command.mcc.code, owner, exclude_id=command.mcc.id)

        async with self._database.transaction():

            # ---------------------------------------------
            # MCC relation IDs
            # ---------------------------------------------

            mcc_relation = await self._mcc_repository.get_relations(
                command.mcc.id
            )

            if mcc_relation is None:
                raise MccNotFoundException()

            # ---------------------------------------------
            # USER
            # ---------------------------------------------
            # The password changes only when the form gives one; a blank field keeps the
            # current one. ProfileService.update hashes it, so the plain text is passed
            # here (hashing it here as well stored a hash of a hash and broke the login).
            new_password = (command.user.password_hash or "").strip() or None
            email = str(command.user.email).strip().lower()

            await self._profile.update(
                user_data=UpdateUserCommand(
                    id=mcc_relation.user_id,
                    name=command.user.name,
                    email=email,
                    mobile=command.user.mobile,
                    role=Role.MCC,
                    is_active=command.user.is_active,
                    password_hash=new_password,
                    updated_by=command.updated_by,
                    profile_image=command.user.profile_image,
                )
            )

            # ---------------------------------------------
            # ADDRESS
            # ---------------------------------------------

            address_id = mcc_relation.address_id

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
                        user_id=mcc_relation.user_id,
                        address_data=CreateAddressCommand(
                            **address_data,
                        ),
                    )

                    address_id = address.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # BANK ACCOUNT
            # ---------------------------------------------

            bank_account_id = mcc_relation.bank_account_id

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
                        user_id=mcc_relation.user_id,
                        bank_data=CreateBankAccountCommand(
                            **bank_data,
                        ),
                    )

                    bank_account_id = bank.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # SETTINGS
            # ---------------------------------------------

            settings_id = mcc_relation.settings_id

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

            quality_id = mcc_relation.milk_quality_config_id

            if command.milk_quality_config:

                if not quality_id:
                    milk_quality_data = command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"])
                    milk_data = MilkQualityConfig(
                            id=uuid4(),
                            user_id=mcc_relation.user_id,
                            **milk_quality_data,
                        )
                    await self._milk_quality_config_repository.create(milk_data)
                    quality_id = milk_data.id
                    await self._database.session.flush()

                else:
                    await self._milk_quality_config_repository.update(
                        MilkQualityConfig(
                            id=quality_id,
                            user_id=mcc_relation.user_id,
                            **command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"]),
                        )
                    )

            # ---------------------------------------------
            # FIXED RATE CONFIG
            # ---------------------------------------------

            fixed_rate_id = mcc_relation.fixed_rate_config_id

            if command.fixed_rate_config:

                if not fixed_rate_id:
                    fixed_rate_data = asdict(command.fixed_rate_config)
                    fixed_rate_data.pop("id")
                    fixed_rate_data.update({"user_id": mcc_relation.user_id})
                    fixed_rate_entity = FixedRateConfig(
                        id=uuid4(),
                        **fixed_rate_data,
                    )
                    await self._fixed_rate_config_repository.create(fixed_rate_entity)
                    fixed_rate_id = fixed_rate_entity.id
                    await self._database.session.flush()

                else:
                    fixed_rate_data = asdict(command.fixed_rate_config)
                    fixed_rate_data.pop("id", None)
                    fixed_rate_data.update({"user_id": mcc_relation.user_id})
                    await self._fixed_rate_config_repository.update(
                        FixedRateConfig(
                            id=fixed_rate_id,
                            **fixed_rate_data,
                        )
                    )

            # ---------------------------------------------
            # MCC
            # ---------------------------------------------

            mcc = await self._mcc_repository.get_by_id(mcc_relation.id, owner=owner)

            if mcc is None:
                raise MccNotFoundException()

            await self._mcc_repository.update(
                replace(mcc,
                    user_id=mcc_relation.user_id,
                    code=command.mcc.code.strip(),
                    name=command.mcc.name.strip(),
                    mcc_type=command.mcc.mcc_type,
                    sample_start=command.mcc.sample_start,
                    sample_end=command.mcc.sample_end,
                    visible_member=(
                        mcc.visible_member if command.mcc.visible_member is None else command.mcc.visible_member
                    ),
                    route_code=command.mcc.route_code,
                    address_id=address_id,
                    bank_account_id=bank_account_id,
                    settings_id=settings_id,
                    milk_quality_config_id=quality_id,
                    fixed_rate_config_id=fixed_rate_id,
                    profile_image=command.mcc.profile_image,
                    is_active=command.mcc.is_active,
                    updated_at=now_naive_ist(),
                    updated_by=command.updated_by,
                ), owner=owner
            )

            await self._database.session.flush()

            if command.device_item_versions is not None:
                from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel
                from sqlalchemy import delete
                
                stmt = delete(DeviceItemVersionModel).where(DeviceItemVersionModel.device_id == mcc_relation.user_id)
                await self._database.session.execute(stmt)
                
                for item in command.device_item_versions:
                    dev_version = DeviceItemVersionModel(
                        id=uuid4(),
                        device_type=1, # 1 for MCC
                        device_id=mcc_relation.user_id,
                        item_name=item.item_name,
                        version=item.version,
                        created_at=now_naive_ist(),
                        updated_at=now_naive_ist(),
                    )
                    self._database.session.add(dev_version)

        return True

    async def update(
        self,
        command: UpdateMccCommand,
        address: str | None = None,
        bank_name: str | None = None,
        account_holder_name: str | None = None,
        account_number: str | None = None,
        ifsc_code: str | None = None,
    ) -> MccDto:
        self._validate(command)

        async with self._database.transaction():
            mcc = await self._mcc_repository.get_by_id(command.id)
            if mcc is None:
                raise MccNotFoundException()

            user = await self._user_repository.get_by_id(mcc.user_id)
            if user is None:
                raise UserNotFoundException()

            now = now_naive_ist()

            # Update Address
            address_id = mcc.address_id
            if address:
                if address_id:
                    address_entity = await self._address_repository.get_by_id(address_id)
                    if address_entity:
                        address_entity.line = address
                        address_entity.updated_at = now
                        await self._address_repository.update(address_entity)
                else:
                    address_id = uuid4()
                    address_entity = Address(
                        id=address_id,
                        user_id=mcc.user_id,
                        line=address,
                        state=None,
                        city=None,
                        pincode=None,
                        created_at=now,
                        updated_at=now,
                    )
                    await self._address_repository.create(address_entity)

            # Update Bank Account
            bank_account_id = mcc.bank_account_id
            if bank_name or account_holder_name or account_number or ifsc_code:
                if bank_account_id:
                    bank_entity = await self._bank_account_repository.get_by_id(bank_account_id)
                    if bank_entity:
                        bank_entity.bank_name = bank_name
                        bank_entity.account_holder = account_holder_name or command.name
                        bank_entity.account_number = account_number
                        bank_entity.ifsc_code = ifsc_code
                        bank_entity.updated_at = now
                        await self._bank_account_repository.update(bank_entity)
                else:
                    bank_account_id = uuid4()
                    bank_entity = BankAccount(
                        id=bank_account_id,
                        user_id=mcc.user_id,
                        account_holder=account_holder_name or command.name,
                        bank_name=bank_name,
                        account_number=account_number,
                        ifsc_code=ifsc_code,
                        created_at=now,
                        updated_at=now,
                    )
                    await self._bank_account_repository.create(bank_entity)

            self._update_user(user, command)
            self._update_mcc(mcc, command, address_id, bank_account_id)

            await self._user_repository.update(user)
            await self._mcc_repository.update(mcc)

        return self._to_dto(mcc)


    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteMccCommand,
    ) -> None:
        async with self._database.transaction():
            mcc = await self._mcc_repository.get_by_id(command.id, command.owner)
            if mcc is None:
                raise MccNotFoundException()

            user = await self._user_repository.get_by_id(mcc.user_id)
            if user is None:
                raise UserNotFoundException()

            self._soft_delete_user(user, command.deleted_by)
            self._soft_delete_mcc(mcc, command.deleted_by)

            # A deleted user's profile image is removed (file + media row)
            await self._profile.delete_profile_image(user.id)
            user.profile_image = None

            await self._user_repository.update(user)
            await self._mcc_repository.update(mcc, owner=command.owner)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetMccQuery,
    ) -> MccDto:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        mcc = await self._mcc_repository.get_by_id(query.id, query.owner)
        if mcc is None:
            raise MccNotFoundException()

        return self._to_dto(mcc)

    async def get_full_detail(
        self,
        query: GetMccQuery,
    ) -> MccDetailDto:
        if query.owner is None:
            raise PermissionError("Owner context is required")
        mcc = await self._mcc_repository.get_by_id(query.id, query.owner)
        if mcc is None:
            raise MccNotFoundException()

        user = await self._user_repository.get_by_id(mcc.user_id)
        if user is None:
            raise UserNotFoundException()

        address = None
        if mcc.address_id:
            address = await self._address_repository.get_by_id(mcc.address_id)

        bank_account = None
        if mcc.bank_account_id:
            bank_account = await self._bank_account_repository.get_by_id(mcc.bank_account_id)

        setting = None
        if mcc.settings_id:
            setting = await self._settings_repository.get_by_id(mcc.settings_id)

        milk_quality_config = None
        if mcc.milk_quality_config_id:
            milk_quality_config = await self._milk_quality_config_repository.get_by_id(mcc.milk_quality_config_id)

        fixed_rate_config = None
        if mcc.fixed_rate_config_id:
            fixed_rate_config = await self._fixed_rate_config_repository.get_by_id(mcc.fixed_rate_config_id)

        return self._to_detail_dto(mcc, user, address, bank_account, setting, milk_quality_config, fixed_rate_config)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListMccQuery, 
    ) -> list[MccListDto]:
        entities = await self._mcc_repository.list_mcc_with_user(
            offset=query.offset,
            limit=query.size,
            keyword=query.keyword,
            owner=query.owner,
            manager=query.manager,
        )
        return entities

    async def for_assigned_list(
        self,
        query: ListMccQuery, 
    ) -> list[MccListDto]:
        entities = await self._mcc_repository.assigned_mcc_with_user(
            offset=query.offset,
            limit=query.size,
            keyword=query.keyword,
            owner= query.owner
        )
        return entities

    async def count(
        self,
        keyword: str | None = None,
        owner: CurrentUser | None = None,
        manager: CurrentUser | None = None,
    ) -> int:
        if keyword:
            return await self._mcc_repository.count_search(keyword, owner, manager=manager)
        return await self._mcc_repository.count(owner, manager=manager)

    async def validate_code(self, code: str, owner: CurrentUser) -> bool:
        """Live form check: same rule as create (code free in the owner's line)."""
        return not await self._mcc_repository.exists_code(code, owner)

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        mcc: Mcc,
    ) -> MccListDto:
        return MccListDto(
            id=mcc.id,
            user_id=mcc.user_id,
            code=mcc.code,
            name=mcc.name,
            mcc_type=mcc.mcc_type,
            is_active=mcc.is_active,
            created_by_name=mcc.created_by_name,
            profile_image=mcc.profile_image,
        )

    def _build_user(self,ixd:UUID, command: CreateMccCommand, now: datetime, created_by: UUID) -> User:
        return User(
            id=ixd,
            name=command.name,
            email=command.email.lower(),
            mobile=command.mobile,
            profile_image=command.profile_image,
            password_hash=self._password.hash(command.password),
            role=Role.MCC,
            created_by=created_by,
            is_active=True,
            is_locked=False,
            created_at=now,
            updated_at=now,
            last_login=now
        )

    def _build_mcc(
        self,
        command: CreateMccCommand,
        user_id: UUID,
        address_id: UUID | None,
        bank_account_id: UUID | None,
        now: datetime | None = None,
        settings_id: UUID | None = None,
        milk_quality_config_id: UUID | None = None,
        rate_config_id: UUID | None = None,
    ) -> Mcc:
        if now is None:
            now = now_naive_ist()
        return Mcc(
            id=uuid4(),
            user_id=user_id,
            code=command.code.strip(),
            name=command.name.strip(),
            mcc_type=command.mcc_type,
            route_code=command.route_code,
            sample_start=command.sample_start,
            sample_end=command.sample_end,
            visible_member=command.visible_member,
            address_id=address_id,
            bank_account_id=bank_account_id,
            settings_id=settings_id,
            milk_quality_config_id=milk_quality_config_id,
            fixed_rate_config_id=rate_config_id,
            profile_image=command.profile_image,
            is_active=True,
            created_by=command.created_by,
            updated_by=command.created_by,
            created_at=now,
            updated_at=now,
        )


    def _validate(
        self,
        command: CreateMccCommand | UpdateMccCommand,
    ) -> None:
        if len(command.name.strip()) < 3:
            raise ValidationException("Invalid MCC Name")

        if command.sample_start > command.sample_end:
            raise ValidationException("Sample range invalid.")

        # Email format validation
        validate_email(command.email)


    def _password_validate(self, password: str|None) -> None:
        # Any password is accepted (any case, length or characters); it only has to be given
        if password is None or not str(password).strip():
            raise ValidateError(message="Password is required.")

    @staticmethod
    def ensure_can_create(owner: CurrentUser | None) -> None:
        """Only Super Admin, Admin and Sub Admin create MCCs (an MCC never creates another MCC)."""
        if owner is None or owner.role_type in (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN):
            return
        if owner.role_type == Role.MCC:
            raise PermissionError("An MCC cannot create another MCC.")
        raise PermissionError("You are not allowed to create an MCC.")

    async def _ensure_code_available(
        self,
        code: str,
        owner: CurrentUser | None,
        exclude_id: UUID | None = None,
    ) -> None:
        """The code must be free in the owner's line (itself, above, below)."""
        if owner is not None and await self._mcc_repository.exists_code(code, owner, exclude_id=exclude_id):
            raise MccCodeAlreadyExistsException(f"MCC code {code.strip()} already exists.")

    async def _ensure_email_available(self, email: str) -> None:
        if await self._user_repository.exists_email(email):
            raise EmailAlreadyExistsException(f"Email {email.strip()} already exists.")

    async def _ensure_mobile_available(self, mobile: str, exclude_user_id: str | None = None) -> None:
        if await self._user_repository.exists_mobile(mobile, exclude_user_id=exclude_user_id):
            raise MobileAlreadyExistsException(f"Mobile number {mobile.strip()} is already registered.")

    def _update_user(
        self,
        user: User,
        command: UpdateMccCommand,
    ) -> None:
        user.name = command.name.strip()
        user.email = command.email.lower()

        if command.password:
            user.password_hash = self._password.hash(command.password)

        user.updated_at = now_naive_ist()
        user.updated_by = command.updated_by

    def _update_mcc(
        self,
        mcc: Mcc,
        command: UpdateMccCommand,
        address_id: UUID | None = None,
        bank_account_id: UUID | None = None,
    ) -> None:
        mcc.code = command.code.strip()
        mcc.name = command.name.strip()
        mcc.mcc_type = command.mcc_type
        mcc.route_code = command.route_code
        mcc.sample_start = command.sample_start
        mcc.sample_end = command.sample_end
        mcc.address_id = address_id
        mcc.bank_account_id = bank_account_id
        mcc.dairy_config_id = command.dairy_config_id
        mcc.rate_config_id = command.rate_config_id
        mcc.profile_image = command.profile_image
        mcc.is_active = command.is_active
        mcc.updated_by = command.updated_by
        mcc.updated_at = now_naive_ist()

    def _soft_delete_mcc(
        self,
        mcc: Mcc,
        deleted_by: UUID,
    ) -> None:
        now = now_naive_ist()
        mcc.is_active = False
        mcc.is_deleted = True
        mcc.deleted_at = now
        mcc.deleted_by = deleted_by
        mcc.updated_at = now

    def _soft_delete_user(
        self,
        user: User,
        deleted_by: UUID,
    ) -> None:
        now = now_naive_ist()
        user.is_active = False
        user.is_deleted = True
        user.deleted_at = now
        user.deleted_by = deleted_by
        user.updated_at = now

    def _to_dto(self, mcc: Mcc) -> MccDto:
        return MccDto(
            id=mcc.id,
            user_id=mcc.user_id,
            code=mcc.code,
            name=mcc.name,
            mcc_type=mcc.mcc_type,
            route_code=mcc.route_code,
            sample_start=mcc.sample_start,
            sample_end=mcc.sample_end,
            visible_member=mcc.visible_member,
            profile_image=mcc.profile_image,
            is_active=mcc.is_active,
            settings_id=mcc.settings_id,
            milk_quality_config_id=mcc.milk_quality_config_id,
            fixed_rate_config_id=mcc.fixed_rate_config_id,
            can_modify=mcc.can_modify,
        )

    def _to_detail_dto(
        self, 
        mcc: Mcc, 
        user: User, 
        address: Address | None, 
        bank_account: BankAccount | None,
        setting: Settings | None = None,
        milk_quality_config: MilkQualityConfig | None = None,
        fixed_rate_config: FixedRateConfig | None = None,
    ) -> MccDetailDto:
        return MccDetailDto(
            user=self._user_repository.to_dto(user) if user else None,
            mcc=self._to_dto(mcc),
            address=AddressMapper.to_dto(address) if address else None,
            bank_account=BankAccountMapper.to_dto(bank_account) if bank_account else None,
            setting=SettingsResponse.model_validate(setting) if setting else None,
            milk_quality_config=MilkQualityConfigResponse.model_validate(milk_quality_config) if milk_quality_config else None,
            fixed_rate_config=FixedRateConfigResponse.model_validate(fixed_rate_config) if fixed_rate_config else None,
        )

    async def partial_update(
        self,
        command: PartialUpdateFullDetailMcc,
        owner: CurrentUser,
    ) -> bool:
        async with self._database.transaction():
            # ---------------------------------------------
            # MCC relation IDs
            # ---------------------------------------------
            mcc_relation = await self._mcc_repository.get_relations(owner.own_id)

            if mcc_relation is None:
                raise MccNotFoundException()

            # ---------------------------------------------
            # USER
            # ---------------------------------------------
            if command.user:
                await self._profile.update(
                    user_data=UpdateUserCommand(
                        id=mcc_relation.user_id,
                        name=command.user.name,
                        email=command.user.email,
                        role=Role.MCC,
                        password_hash=None,
                        mobile=command.user.mobile,
                        updated_by=command.updated_by,
                    )
                )

            # ---------------------------------------------
            # ADDRESS
            # ---------------------------------------------
            address_id = mcc_relation.address_id

            if command.address:
                address_data = asdict(command.address) if is_dataclass(command.address) else (command.address.model_dump(exclude_unset=True) if hasattr(command.address, "model_dump") else dict(command.address))

                if address_id:
                    await self._profile.address_update(
                        UpdateAddressCommand(
                            id=address_id,
                            **address_data,
                        )
                    )
                else:
                    address = await self._profile.create_address(
                        user_id=mcc_relation.user_id,
                        address_data=CreateAddressCommand(
                            **address_data,
                        ),
                    )
                    address_id = address.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # BANK ACCOUNT
            # ---------------------------------------------
            bank_account_id = mcc_relation.bank_account_id

            if command.bank_account:
                bank_data = asdict(command.bank_account) if is_dataclass(command.bank_account) else (command.bank_account.model_dump(exclude_unset=True) if hasattr(command.bank_account, "model_dump") else dict(command.bank_account))

                if bank_account_id:
                    await self._profile.bank_update(
                        UpdateBankAccountCommand(
                            id=bank_account_id,
                            **bank_data,
                        )
                    )
                else:
                    bank = await self._profile.create_bank_account(
                        user_id=mcc_relation.user_id,
                        bank_data=CreateBankAccountCommand(
                            **bank_data,
                        ),
                    )
                    bank_account_id = bank.id
                    await self._database.session.flush()

            # ---------------------------------------------
            # SETTINGS
            # ---------------------------------------------
            settings_id = mcc_relation.settings_id

            if command.setting:
                setting_data = asdict(command.setting) if is_dataclass(command.setting) else (command.setting.model_dump(exclude_unset=True) if hasattr(command.setting, "model_dump") else dict(command.setting))

                if not settings_id:
                    setting = await self._settings_repository.create(
                        Settings(
                            id=uuid4(),
                            **setting_data,
                        )
                    )
                    settings_id = setting.id
                    await self._database.session.flush()
                else:
                    await self._settings_repository.update(
                        Settings(
                            id=settings_id,
                            **setting_data,
                        )
                    )

            # ---------------------------------------------
            # MILK QUALITY CONFIG
            # ---------------------------------------------
            quality_id = mcc_relation.milk_quality_config_id

            if command.milk_quality_config:
                if hasattr(command.milk_quality_config, "model_dump"):
                    milk_quality_data = command.milk_quality_config.model_dump(exclude_unset=True, exclude=["id", "user_id"])
                elif is_dataclass(command.milk_quality_config):
                    milk_quality_data = {k: v for k, v in asdict(command.milk_quality_config).items() if k not in ("id", "user_id") and v is not None}
                else:
                    milk_quality_data = {k: v for k, v in dict(command.milk_quality_config).items() if k not in ("id", "user_id") and v is not None}

                if not quality_id:
                    milk_data = MilkQualityConfig(
                        id=uuid4(),
                        user_id=mcc_relation.user_id,
                        **milk_quality_data,
                    )
                    await self._milk_quality_config_repository.create(milk_data)
                    quality_id = milk_data.id
                    await self._database.session.flush()
                else:
                    await self._milk_quality_config_repository.update(
                        MilkQualityConfig(
                            id=quality_id,
                            user_id=mcc_relation.user_id,
                            **milk_quality_data,
                        )
                    )

            # ---------------------------------------------
            # FIXED RATE CONFIG
            # ---------------------------------------------
            fixed_rate_id = mcc_relation.fixed_rate_config_id

            if hasattr(command, "fixed_rate_config") and command.fixed_rate_config:
                if hasattr(command.fixed_rate_config, "model_dump"):
                    fixed_rate_data = command.fixed_rate_config.model_dump(exclude_unset=True, exclude=["id", "user_id"])
                elif is_dataclass(command.fixed_rate_config):
                    fixed_rate_data = {k: v for k, v in asdict(command.fixed_rate_config).items() if k not in ("id", "user_id") and v is not None}
                else:
                    fixed_rate_data = {k: v for k, v in dict(command.fixed_rate_config).items() if k not in ("id", "user_id") and v is not None}

                if not fixed_rate_id:
                    fixed_rate_entity = FixedRateConfig(
                        id=uuid4(),
                        user_id=mcc_relation.user_id,
                        **fixed_rate_data,
                    )
                    await self._fixed_rate_config_repository.create(fixed_rate_entity)
                    fixed_rate_id = fixed_rate_entity.id
                    await self._database.session.flush()
                else:
                    await self._fixed_rate_config_repository.update(
                        FixedRateConfig(
                            id=fixed_rate_id,
                            user_id=mcc_relation.user_id,
                            **fixed_rate_data,
                        )
                    )

            # ---------------------------------------------
            # MCC
            # ---------------------------------------------
            mcc = await self._mcc_repository.get_by_id(mcc_relation.id, owner=owner)

            if mcc is None:
                raise MccNotFoundException()

            await self._mcc_repository.update(
                replace(
                    mcc,
                    user_id=mcc_relation.user_id,
                    address_id=address_id,
                    bank_account_id=bank_account_id,
                    settings_id=settings_id,
                    milk_quality_config_id=quality_id,
                    fixed_rate_config_id=fixed_rate_id,
                    updated_at=now_naive_ist(),
                    updated_by=command.updated_by,
                ),
                owner=owner,
            )

            await self._database.session.flush()

            if command.device_item_versions is not None:
                from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel
                from sqlalchemy import delete

                stmt = delete(DeviceItemVersionModel).where(DeviceItemVersionModel.device_id == mcc_relation.user_id)
                await self._database.session.execute(stmt)

                for item in command.device_item_versions:
                    dev_version = DeviceItemVersionModel(
                        id=uuid4(),
                        device_type=1,  # 1 for MCC
                        device_id=mcc_relation.user_id,
                        item_name=item.item_name,
                        version=item.version,
                        created_at=now_naive_ist(),
                        updated_at=now_naive_ist(),
                    )
                    self._database.session.add(dev_version)

        return True

