from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.farmer.domain.entities import Farmer


class IFarmerRepository(ABC):

    @abstractmethod
    async def create(
        self,
        entity: Farmer,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: Farmer,
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
    ) -> Farmer | None:
        ...

    @abstractmethod
    async def get_by_code(
        self,
        code: str,
    ) -> Farmer | None:
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
    ) -> list[Farmer]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[Farmer]:
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
