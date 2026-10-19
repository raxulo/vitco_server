from app.modules.administration.domain.entities import User
from abc import ABC
from abc import abstractmethod


class IUserRepository(ABC):

    @abstractmethod
    async def create(
        self,
        user: User,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        user: User,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        user_id,
    ) -> None:
        ...

    @abstractmethod
    async def get_by_id(
        self,
        user_id,
    ) -> User | None:
        ...

    @abstractmethod
    async def get_by_email(
        self,
        email: str,
    ) -> User | None:
        ...

    @abstractmethod
    async def exists_email(
        self,
        email: str,
    ) -> bool:
        ...

    @abstractmethod
    async def exists_mobile(
        self,
        mobile: str,
        exclude_user_id: str | None = None,
    ) -> bool:
        ...

    @abstractmethod
    async def list(
        self,
    ) -> list[User]:
        ...