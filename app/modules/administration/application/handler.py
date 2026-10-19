"""
Administration

User Application Service

Python 3.13+
"""

from app.modules.administration.domain.enums import Role
from app.config.settings import settings
from app.modules.administration.application.command import GetUserQuery
from app.modules.administration.application.command import ListUsersQuery
from app.modules.administration.application.command import DeleteUserCommand
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.administration.domain.exceptions import UserNotFoundException
from app.modules.administration.domain.exceptions import EmailNotFoundException
from uuid import uuid4
from datetime import UTC, datetime
from app.modules.administration.domain.entities import User
from app.modules.administration.domain.exceptions import UserAlreadyExistsException
from fastapi.exceptions import ValidationException
from app.modules.administration.domain.entities import UserDto
from app.modules.administration.application.command import CreateUserCommand
from app.modules.auth.application.command import LoginCommand
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.administration.infrastructure.repository import UserRepository
from app.core.database.manager import DatabaseManager

class UserHandler:

    __slots__ = ("_database","_repository","_password")

    def __init__(
        self,
        database: DatabaseManager,
        repository: UserRepository,
        password: PasswordService,
    ):

        self._database = database
        self._repository = repository
        self._password = password

    # =====================================================
    # CRUD
    # =====================================================

    async def create_super_admin(

        self,

    ) -> UserDto:

        # Already exists
        if await self._repository.exists_super_admin():
            return

        command = CreateUserCommand(
            name=settings.ADMIN_NAME,
            email=settings.ADMIN_EMAIL,
            password_hash=settings.ADMIN_PASSWORD,
            role=Role.SUPER_ADMIN,
            is_active=True,
            is_locked=False,
        )
        return await self.create(command)

    async def create(self, command: CreateUserCommand,) -> UserDto:

        self._validate_create(command)
        await self._ensure_email_available(command.email)
        if command.mobile and command.mobile.strip():
            await self._ensure_mobile_available(command.mobile.strip())
        
        password_hash = self._password.hash(command.password_hash)
        user = self._build_user(command, password_hash)

        async with self._database.transaction():
            await self._repository.create(user)

            # await self._write_audit_log(
            #     user=user,
            #     action="CREATE",
            # )

        return self._to_dto(user)

    async def update(
        self,
        command: UpdateUserCommand,

    ) -> UserDto:

        # self._validate_update(command)

        async with self._database.transaction():

            user = await self._repository.get_by_id(id=command.id)

            if user is None:
                raise UserNotFoundException()

            if command.mobile and command.mobile.strip():
                await self._ensure_mobile_available(command.mobile.strip(), exclude_user_id=str(user.id))

            self._update_entity(user,command)
            await self._repository.update(user)
        return self._to_dto(user)

    async def delete(
        self,
        command: DeleteUserCommand,
    ) -> None:

        async with self._database.transaction():

            user = await self._repository.get_by_id(id=command.id)

            if user is None:
                raise UserNotFoundException()


            await self._repository.delete(user.id)

            # await self._write_audit_log(
            #     user=user,
            #     action="DELETE",
            # )

    # =====================================================
    # Query
    # =====================================================

    async def get(
        self,
        query: GetUserQuery,
    ) -> UserDto:

        user = await self._repository.get_by_id(query.id)
        if user is None:
            raise UserNotFoundException()
        return self._to_dto(user)


    async def list(
        self,
        query: ListUsersQuery,
    ):

        return await self._repository.list(query)

    async def search(
        self,
        keyword: str,
    ):

        return await self._repository.search(
            keyword
        )

    # =====================================================
    # Status
    # =====================================================

    async def enable(
        self,
        user_id,
    ):

        ...

    async def disable(
        self,
        user_id,
    ):

        ...

    async def lock(
        self,
        user_id,
    ):

        ...

    async def unlock(
        self,
        user_id,
    ):

        ...

    # =====================================================
    # Profile
    # =====================================================

    async def profile(
        self,
        user_id,
    ):

        ...

    async def update_profile(
        self,
        command,
    ):

        ...

    async def upload_avatar(
        self,
        user_id,
        file,
    ):

        ...

    def _validate_create(
        self,
        command: CreateUserCommand,
    ):

        if len(command.name.strip()) < 3:
            raise ValidationException(
                "Invalid Name"
            )

        if len(command.password_hash) < 8:
            raise ValidationException(
                "Password too short."
            )

    async def _ensure_email_available(self, email: str):
        exists = await self._repository.exists_email(email)
        if exists:
            raise UserAlreadyExistsException()

    async def _ensure_mobile_available(self, mobile: str, exclude_user_id: str | None = None):
        exists = await self._repository.exists_mobile(mobile, exclude_user_id=exclude_user_id)
        if exists:
            raise ValidationException("Mobile number is already registered. Mobile number must be unique.")

    async def _email_not_found(self, email: str):
        exists = await self._repository.exists_email(email)
        if not exists:
            raise EmailNotFoundException()


    def _build_user(self, command: CreateUserCommand, password_hash: str) -> User:
        now = datetime.now(UTC)
        return User(
            id=uuid4(),
            name=command.name.strip(),
            email=command.email.lower(),
            mobile=command.mobile,
            password_hash=password_hash,
            role=command.role,
            is_active=True,
            is_locked=False,
            last_login=None,
            created_at=now,
            updated_at=now,
            created_by=None,
        )


    def _to_dto(
        self,
        user: User,
    ) -> UserDto:

        return UserDto(

            id=user.id,

            name=user.name,

            email=user.email,

            mobile=user.mobile,
            role=user.role,

            is_active=user.is_active,
            created_by=user.created_by,
            is_locked=user.is_locked,
            created_at=user.created_at,
            profile_image=user.profile_image,
        )

    def _update_entity(
        self,
        user: User,
        command: UpdateUserCommand,
    ) -> None:

        user.name = command.name.strip()
        user.email = command.email.lower()
        user.mobile = command.mobile
        user.role_id = command.role_id
        user.is_active = command.is_active
        user.updated_at = datetime.now(UTC)