from app.core.clock import now_naive_ist
from app.modules.media.application.services import MediaUrlService
from app.modules.media.domain.enums import MediaCategory
from app.modules.media.application.services import MediaService
from dataclasses import replace
from app.modules.administration.domain.exceptions import UserNotFoundException
from app.modules.common.bank.domain.exceptions import BankAccountNotFoundException
from app.modules.common.address.domain.exceptions import AddressNotFoundException
from app.core.validators import mobile_number
from app.modules.administration.domain.exceptions import (
    EmailAlreadyExistsException,
    InvalidMobileException,
    MobileAlreadyExistsException,
)
from uuid import UUID
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.common.bank.domain.entities import BankAccount
from app.modules.common.address.domain.entities import Address
from app.modules.administration.domain.entities import Brand, User
from app.core.exceptions.base import ValidateError
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

        # Every user needs a valid 10-digit mobile; email and mobile are unique across users
        user_data.mobile = self._required_mobile(user_data.mobile)
        await self.ensure_contact_available(email=user_data.email, mobile=user_data.mobile)

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
        # A user has one bank account: when one already exists (e.g. its link on the
        # MCC / VLCC / farmer row was lost) update that row instead of inserting a second
        existing = await self._bank_repository.get_by_user_id(user_id)
        if existing is not None:
            return await self.bank_update(
                UpdateBankAccountCommand(
                    id=existing.id,
                    account_holder=bank_data.account_holder,
                    bank_name=bank_data.bank_name,
                    account_number=bank_data.account_number,
                    ifsc_code=bank_data.ifsc_code,
                    upi_id=bank_data.upi_id,
                )
            )
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
        # addresses.user_id is unique: reuse the user's existing address row
        existing = await self._address_repository.get_by_user_id(user_id)
        if existing is not None:
            return await self.address_update(
                UpdateAddressCommand(
                    id=existing.id,
                    line=address_data.line,
                    state=address_data.state,
                    city=address_data.city,
                    pincode=address_data.pincode,
                )
            )
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

        current = await self._user_repository.get_by_id(user_data.id)

        # A new mobile must be valid; leaving it out keeps the current one, which must exist
        if user_data.mobile is not None and str(user_data.mobile).strip():
            user_data.mobile = self._required_mobile(user_data.mobile)
        else:
            user_data.mobile = None
            if current is not None and not (current.mobile or "").strip():
                raise InvalidMobileException()

        # Only a changed email / mobile is checked: re-saving a record with its own
        # (even legacy-duplicated) values never reports "already exists"
        email_changed = bool(user_data.email) and (
            current is None or str(user_data.email).strip().lower() != (current.email or "").strip().lower()
        )
        mobile_changed = bool(user_data.mobile) and (
            current is None or str(user_data.mobile).strip() != (current.mobile or "").strip()
        )
        await self.ensure_contact_available(
            email=user_data.email if email_changed else None,
            mobile=user_data.mobile if mobile_changed else None,
            exclude_user_id=user_data.id,
        )

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

    async def save_brand(
        self,
        *,
        admin_id: UUID,
        enabled: bool,
        logo=None,
        uploaded_by: UUID | None = None,
    ) -> None:
        """
        Apply an Admin's Self Brand switch; call inside the caller's transaction.

        Off: the stored logo is deleted. On with a new file: the new logo replaces the
        old one. On without a file: the current logo (if any) stays.
        """
        if not enabled:
            await self._media_service.delete_brand_logos(admin_id)
            await self._user_repository.set_brand(admin_id, enabled=False, logo_url=None)
            return

        current = await self._user_repository.get_by_id(admin_id)
        logo_url = current.brand_logo if current else None
        if self._has_upload(logo):
            try:
                media = await self._media_service.upload_brand_logo(
                    file=logo, admin_id=admin_id, uploaded_by=uploaded_by
                )
            except ValueError as exc:
                raise ValidateError(str(exc)) from exc
            await self._media_service.delete_brand_logos(admin_id, keep_media_id=media.id)
            logo_url = MediaUrlService().build(storage_key=media.storage_key)

        await self._user_repository.set_brand(admin_id, enabled=True, logo_url=logo_url)

    async def brand_of(self, owner) -> Brand:
        """The Self Brand `owner` works under (see UserRepository.brand_of)."""
        return await self._user_repository.brand_of(owner)

    async def delete_profile_image(self, user_id: UUID) -> None:
        """Remove a user's profile image files and rows (used when the user is deleted)."""
        await self._media_service.delete_profile_image(user_id)

    @staticmethod
    def _required_mobile(mobile: str | None) -> str:
        """A mobile number is mandatory for every user: exactly 10 digits."""
        try:
            return mobile_number(mobile, required=True)
        except ValueError as exc:
            raise InvalidMobileException(str(exc) + ".") from exc

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

    async def ensure_contact_available(
        self,
        *,
        email: str | None,
        mobile: str | None,
        exclude_user_id: UUID | None = None,
    ) -> None:
        """
        Email and mobile number must never be shared by two users.
        On update pass the user's own id so its current values are not a clash.
        """
        if email and await self._user_repository.exists_email(email, exclude_user_id=exclude_user_id):
            raise EmailAlreadyExistsException(f"Email {email.strip()} already exists.")
        if mobile and str(mobile).strip() and await self._user_repository.exists_mobile(
            str(mobile).strip(), exclude_user_id=exclude_user_id
        ):
            raise MobileAlreadyExistsException(f"Mobile number {str(mobile).strip()} is already registered.")

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