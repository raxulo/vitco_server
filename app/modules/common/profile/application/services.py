from app.core.clock import now_naive_ist
from app.modules.media.application.services import MediaUrlService
from app.modules.media.domain.enums import MediaCategory
from app.modules.media.application.services import MediaService
from dataclasses import replace
from app.modules.administration.domain.exceptions import UserNotFoundException
from app.modules.common.bank.domain.exceptions import BankAccountNotFoundException
from app.modules.common.address.domain.exceptions import AddressNotFoundException
from app.modules.administration.domain.exceptions import UserAlreadyExistsException
from uuid import UUID
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.common.bank.domain.entities import BankAccount
from app.modules.common.address.domain.entities import Address
from app.modules.administration.domain.entities import User
from datetime import UTC
from datetime import datetime
from uuid import uuid4
from app.modules.common.profile.application.command import CreatedProfile
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.administration.application.command import CreateUserCommand
from app.modules.administration.domain.enums import Role
from app.modules.common.bank.infrastructure.repository import BankAccountRepository
from app.modules.common.address.infrastructure.repository import AddressRepository
from app.modules.administration.infrastructure.repository import UserRepository
from app.core.database.manager import DatabaseManager
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.common.profile.application.command import CreatedProfile
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.administration.application.command import CreateUserCommand
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.mapper import UserMapper

class ProfileService:
    def __init__(
        self,
        database: DatabaseManager,
        user_repository: UserRepository,
        address_repository: AddressRepository,
        bank_repository: BankAccountRepository,
        media_service: MediaService,
        password: PasswordService,
    ) -> None:
        self._database = database
        self._user_repository = user_repository
        self._address_repository = address_repository
        self._bank_repository = bank_repository
        self._media_service = media_service
        self._password = password

    async def create(
        self,
        *,
        user_data: CreateUserCommand,
        address_data: CreateAddressCommand | None = None,
        bank_data: CreateBankAccountCommand | None = None,
        role: Role,
    ) -> CreatedProfile:

        user_id = uuid4()
        now = now_naive_ist()

        user = User(
            id=user_id,
            name=user_data.name,
            email=user_data.email,
            mobile=user_data.mobile,
            password_hash=(
                self._password.hash(user_data.password_hash)
                if user_data.password_hash
                else None
            ),
            role=role,
            is_active=True,
            is_locked=False,
            created_at=now,
            updated_at=now,
            created_by=user_data.created_by,
            profile_image=None,
        )

        db_model = UserMapper.to_model(user)
        self._user_repository._session.add(db_model)
        await self._user_repository._session.flush()

        if self._has_upload(user_data.profile_image):
            # Stored in this user's own folder (profile/<user_id>/), compressed to <= 100 KB
            media_model = await self._media_service.upload_profile_image(file=user_data.profile_image, user_id=user_id)
            image_url = MediaUrlService().build(storage_key=media_model.storage_key)
            db_model.profile_url = image_url
            user = replace(user, profile_image=image_url)
            await self._user_repository._session.flush()

        address = None

        if address_data:
            address = await self.create_address(
                user_id=user_id,
                address_data=address_data,
            )

        bank = None

        if bank_data:
            bank = await self.create_bank_account(
                user_id=user_id,
                bank_data=bank_data,
            )

        return CreatedProfile(
            user=user,
            address=address,
            bank_account=bank,
        )

    async def create_bank_account(
        self, *,
        user_id: UUID,
        bank_data: CreateBankAccountCommand,
    ) -> BankAccount:
        now = now_naive_ist()
        bank = BankAccount(
            id=uuid4(),
            user_id=user_id,
            bank_name=bank_data.bank_name,
            account_holder=bank_data.account_holder,
            account_number=bank_data.account_number,
            ifsc_code=bank_data.ifsc_code,
            upi_id=bank_data.upi_id,
            created_at=now,
        )
        await self._bank_repository.create(bank)
        return bank

    async def create_address(
        self, *,
        user_id: UUID,
        address_data: CreateAddressCommand,
    ) -> Address:
        now = now_naive_ist()
        address = Address(
            id=uuid4(),
            user_id=user_id,
            line=address_data.line,
            city=address_data.city,
            state=address_data.state,
            pincode=address_data.pincode,
            created_at=now,
        )
        await self._address_repository.create(address)
        return address

    async def update(
        self, *,
        user_data: UpdateUserCommand,
        address_data: UpdateAddressCommand | None = None,
        bank_data: UpdateBankAccountCommand | None = None,
    ) -> None:

        if user_data.password_hash:
            user_data.password_hash = self._password.hash(user_data.password_hash)

        if self._has_upload(user_data.profile_image):
            # Upload the new image first, then remove the old one(s), so a failed
            # upload never leaves the user without a picture
            media_model = await self._media_service.upload_profile_image(file=user_data.profile_image, user_id=user_data.id)
            await self._media_service.delete_profile_image(user_data.id, keep_media_id=media_model.id)
            user_data.profile_image = MediaUrlService().build(storage_key=media_model.storage_key)

        else:
            # No new file: keep the current picture (None is not written by user_update)
            user_data.profile_image = None

        user = await self._user_repository.user_update(user_data)
        if not user:
            raise UserNotFoundException()

        if address_data and address_data.id:
                await self.address_update(address_data)

        if bank_data and bank_data.id:
                await self.bank_update(bank_data)

    async def delete_profile_image(self, user_id: UUID) -> None:
        """Remove a user's profile image files and rows (used when the user is deleted)."""
        await self._media_service.delete_profile_image(user_id)

    @staticmethod
    def _has_upload(file) -> bool:
        return bool(file is not None and getattr(file, "filename", None))

    async def get_profile(self, user_id: UUID) -> CreatedProfile:
        user = await self._user_repository.get_by_id(user_id)
        address = await self._address_repository.get_by_user_id(user_id)
        bank = await self._bank_repository.get_by_user_id(user_id)
        return CreatedProfile(
            user=user,
            address=address,
            bank_account=bank,
        )

    async def _ensure_email_available(self, email: str) -> None:
        if await self._user_repository.exists_email(email):
            raise UserAlreadyExistsException()

    async def address_update(self, data: UpdateAddressCommand) -> Address:
        result = await self._address_repository.update_address_by_command(data)
        if not result:
            raise AddressNotFoundException()
        return result

    async def bank_update(self, data: UpdateBankAccountCommand) -> BankAccount:
        result = await self._bank_repository.update_bank_by_command(data)
        if not result:
            raise BankAccountNotFoundException()
        return result