"""
Auth Infrastructure Repository

Python 3.13+
SQLAlchemy 2.x
"""

from app.core.database import DatabaseManager
from sqlalchemy import select

from app.modules.auth.domain.entities import User
from app.modules.auth.domain.repository import UserRepository as UserRepositoryInterface
from app.modules.auth.infrastructure.models import UserModel
from app.modules.auth.infrastructure.mapper import UserMapper


class UserRepository(UserRepositoryInterface):
    """
    Stateless Repository implementing domain UserRepository interface.
    """

    __slots__ = (
        "_database",
    )

    def __init__(
        self,
        database: DatabaseManager,
    ):
        self._database = database

    async def get_by_id(
        self,
        user_id: str,
    ) -> User | None:
        stmt = (
            select(
                UserModel.id,
                UserModel.email,
                UserModel.username,
                UserModel.password_hash,
                UserModel.is_active,
                UserModel.is_verified,
            )
            .where(UserModel.id == user_id)
            .limit(1)
        )
        row = (await self._database.session.execute(stmt)).first()
        if row is None:
            return None
        return User(
            id=row.id,
            email=row.email,
            username=row.username,
            password_hash=row.password_hash,
            is_active=row.is_active,
            is_verified=row.is_verified,
        )

    async def get_by_email(
        self,
        email: str,
    ) -> User | None:

        stmt = (
            select(
                UserModel.id,
                UserModel.email,
                UserModel.username,
                UserModel.password_hash,
                UserModel.is_active,
                UserModel.is_verified,
            )
            .where(UserModel.email == email)
            .limit(1)
        )

        row = (
            await self._database.session.execute(stmt)
        ).first()

        if row is None:
            return None

        return User(
            id=row.id,
            email=row.email,
            username=row.username,
            password_hash=row.password_hash,
            is_active=row.is_active,
            is_verified=row.is_verified,
        )

    async def exists_by_email(
        self,
        email: str,
    ) -> bool:
        stmt = select(UserModel.id).where(UserModel.email == email).limit(1)
        row = (await self._database.session.execute(stmt)).first()
        return row is not None

    async def create(
        self,
        user: User,
    ) -> User:
        model = UserMapper.to_model(user)
        self._database.session.add(model)
        await self._database.session.flush()
        return UserMapper.to_entity(model)

    async def update(
        self,
        user: User,
    ) -> User:
        model = await self._database.session.get(UserModel, user.id)
        if model is None:
            raise ValueError(f"User not found: {user.id}")
        UserMapper.update_model(model, user)
        await self._database.session.flush()
        return UserMapper.to_entity(model)

    async def delete(
        self,
        user_id: str,
    ) -> None:
        from sqlalchemy import delete
        stmt = delete(UserModel).where(UserModel.id == user_id)
        await self._database.session.execute(stmt)
        await self._database.session.flush()