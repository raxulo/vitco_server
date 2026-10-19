from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.vlcc.domain.entities import Vlcc


class IVlccRepository(ABC):

    @abstractmethod
    async def create(
        self,
        entity: Vlcc,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: Vlcc,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        id: UUID,
    ) -> None:
        ...

    @abstractmethod
    async def get_by_id(
        self,
        id: UUID,
    ) -> Vlcc | None:
        ...

    @abstractmethod
    async def get_by_code(
        self,
        code: str,
    ) -> Vlcc | None:
        ...

    @abstractmethod
    async def exists_code(
        self,
        code: str,
    ) -> bool:
        ...

    @abstractmethod
    async def exists_user(
        self,
        user_id: UUID,
    ) -> bool:
        ...

    @abstractmethod
    async def list(
        self,
        offset: int,
        limit: int,
    ) -> list[Vlcc]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[Vlcc]:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...

    @abstractmethod
    async def count_search(
        self,
        keyword: str,
    ) -> int:
        ...
