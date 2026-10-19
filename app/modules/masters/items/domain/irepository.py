from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.masters.items.domain.entities import ItemMaster


class IItemMasterRepository(ABC):

    @abstractmethod
    async def create(
        self,
        entity: ItemMaster,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: ItemMaster,
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
    ) -> ItemMaster | None:
        ...

    @abstractmethod
    async def get_by_code(
        self,
        code: int,
    ) -> ItemMaster | None:
        ...

    @abstractmethod
    async def exists_code(
        self,
        code: int,
    ) -> bool:
        ...

    @abstractmethod
    async def list(
        self,
        offset: int,
        limit: int,
    ) -> list[ItemMaster]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[ItemMaster]:
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
