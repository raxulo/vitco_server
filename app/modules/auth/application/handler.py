"""
Auth Application Request Handler

Python 3.13+
"""

from app.modules.administration.domain.enums import Role
from app.modules.administration.domain.entities import User
from dataclasses import dataclass

from app.modules.auth.application.command import LoginCommand
from app.modules.auth.domain.exceptions import (
    InvalidCredentials,
    EmailNotVerified,
    AccountDisabled,
)

from app.modules.auth.infrastructure.password import PasswordService
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.administration.infrastructure.repository import UserRepository


@dataclass(slots=True, frozen=True)
class LoginResult:
    id: str
    access_token: str
    refresh_token: str
    token_type: str
    user_id: str
    email: str
    full_name: str
    role: Role

class LoginHandler:
    """
    Stateless Singleton
    Thread Safe
    High Performance
    """

    __slots__ = (
        "_repository",
        "_password",
        "_jwt",
    )

    def __init__(
        self,
        repository: UserRepository,
        password_service: PasswordService,
        jwt_service: JWTService,
    ) -> None:

        self._repository = repository
        self._password = password_service
        self._jwt = jwt_service

    async def execute(self,*,command: LoginCommand) -> LoginResult:

        user: User = await self._repository.get_by_email(email=command.email)

        if user is None:
            raise InvalidCredentials()

        if not self._password.verify(
            password=command.password,
            password_hash=user.password_hash,
        ):
            raise InvalidCredentials()

        if not user.is_active:
            raise AccountDisabled()

        user_id = str(user.id)

        token = self._jwt.create_access_token(user_id, {"role": user.role.value, "own_id": str(user.own_id or ""), "name": user.name, "profile_image": user.profile_image})

        return LoginResult(
            id=str(user.own_id or ""),
            access_token=token,
            refresh_token=self._jwt.create_refresh_token(user_id),
            token_type="Bearer",
            user_id=user_id,
            email=user.email,
            full_name=user.name,
            role=user.role
        )

    async def login(self,*,command: LoginCommand) -> LoginResult:

        user: User = await self._repository.get_by_email(email=command.email)

        if user is None:
            raise InvalidCredentials()

        if not self._password.verify(
            password=command.password,
            password_hash=user.password_hash,
        ):
            raise InvalidCredentials()

        if not user.is_active:
            raise AccountDisabled()

        user_id = str(user.id)

        token = self._jwt.create_access_token(user_id, {"role": user.role.value, "own_id": str(user.own_id or ""), "name": user.name, "profile_image": user.profile_image})
        
        return LoginResult(
            id=str(user.own_id or ""),
            access_token=token,
            refresh_token=token,
            token_type="Bearer",
            user_id=user_id,
            email=user.email,
            full_name=user.name,
            role=user.role
        )