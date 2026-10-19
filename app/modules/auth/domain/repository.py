from abc import ABC, abstractmethod

from .entities import User


class UserRepository:

    @abstractmethod
    async def get_by_id(
        self, session,
        user_id: str,
    ) -> User | None:
        ...

    @abstractmethod
    async def get_by_email(
        self, session,
        email: str,
    ) -> User | None:
        ...

    @abstractmethod
    async def exists_by_email(
        self, session,
        email: str,
    ) -> bool:
        ...

    @abstractmethod
    async def create(
        self, session,
        user: User,
    ) -> User:
        ...

    @abstractmethod
    async def update(
        self, session,
        user: User,
    ) -> User:
        ...

    @abstractmethod
    async def delete(
        self, session,
        user_id: str,
    ) -> None:
        ...