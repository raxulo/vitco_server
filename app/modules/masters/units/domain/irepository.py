from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.masters.units.domain.entities import UnitMaster


class IUnitMasterRepository(ABC):

    @abstractmethod
    async def create(
        self,
        entity: UnitMaster,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: UnitMaster,
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
    ) -> UnitMaster | None:
        ...

    @abstractmethod
    async def get_by_name(
        self,
        name: str,
    ) -> UnitMaster | None:
        ...

    @abstractmethod
    async def exists_name(
        self,
        name: str,
    ) -> bool:
        ...

    @abstractmethod
    async def list(
        self,
        offset: int,
        limit: int,
    ) -> list[UnitMaster]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[UnitMaster]:
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
