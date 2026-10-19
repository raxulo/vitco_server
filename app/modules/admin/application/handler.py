from app.modules.administration.domain.enums import Role
from app.modules.administration.domain.repository import IUserRepository
from app.modules.administration.domain.entities import User
from app.modules.auth.domain.exceptions import EmailNotVerified
from app.modules.auth.domain.exceptions import AccountDisabled
from app.modules.auth.domain.exceptions import InvalidCredentials
from app.modules.auth.application.handler import LoginResult
from app.modules.auth.application.command import LoginCommand
from app.config.settings import settings
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.admin.infrastructure.models import Admin
from app.modules.admin.domain.enums import AdminRole
from app.modules.admin.domain.repository import IAdminRepository


from app.modules.common.profile.application.services import ProfileService
from app.modules.common.profile.application.command import CreatedProfile
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from uuid import UUID

class AdminHandler:

    def __init__(

        self,

        repository: IAdminRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
        profile_service: ProfileService,

    ):

        self._repository = repository
        self._password_service = password_service
        self._jwt_service = jwt_service
        self._profile_service = profile_service

    async def get_full_detail(self, user_id: UUID) -> CreatedProfile:
        return await self._profile_service.get_profile(user_id)

    async def update(
        self,
        user_data: UpdateUserCommand,
        address_data: UpdateAddressCommand | None = None,
        bank_data: UpdateBankAccountCommand | None = None,
    ) -> None:
        await self._profile_service.update(
            user_data=user_data,
            address_data=address_data,
            bank_data=bank_data,
        )

    async def create_super_admin(

        self,

    ) -> User:

        # Already exists
        if await self._repository.exists_super_admin():
            return

        admin = User(
            name=settings.ADMIN_NAME,
            email=settings.ADMIN_EMAIL,
            password_hash=self._password_service.hash(settings.ADMIN_PASSWORD),
            role=Role.SUPER_ADMIN,
            is_active=True,
            is_locked=False,
        )

        return await self._repository.create(admin)

    async def login(self,*,command: LoginCommand) -> LoginResult:

        user: Admin = await self._repository.get_by_email(email=command.email)

        if user is None:
            raise InvalidCredentials()

        if not self._password_service.verify(
            password=command.password,
            password_hash=user.password,
        ):
            raise InvalidCredentials()

        if not user.is_active:
            raise AccountDisabled()

        user_id = str(user.id)

        token = self._jwt_service.create_access_token(user_id, {"role": str(user.role)})
        
        return LoginResult(
            access_token=token,
            refresh_token=self._jwt_service.create_refresh_token(user_id),
            token_type="Bearer",
            user_id=user_id,
            email=user.email,
            full_name=user.name,
        )