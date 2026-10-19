from fastapi import Depends

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import get_db

from modules.auth.infrastructure.database.repository import (
    SQLAlchemyUserRepository,
)

from modules.auth.infrastructure.security.jwt import (
    JWTService,
)

from modules.auth.infrastructure.security.password import (
    PasswordService,
)

from modules.auth.application.login.handler import (
    LoginHandler,
)


def get_login_handler(

    db: AsyncSession = Depends(get_db),

):

    repository = SQLAlchemyUserRepository(db)

    return LoginHandler(

        repository=repository,

        jwt=JWTService(),

        password=PasswordService(),

    )