from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.masters.route.domain.entities import RouteMaster


class IRouteMasterRepository(ABC):

    @abstractmethod
    async def create(
        self,
        entity: RouteMaster,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: RouteMaster,
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
    ) -> RouteMaster | None:
        ...

    @abstractmethod
    async def get_by_code(
        self,
        code: int,
    ) -> RouteMaster | None:
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
    ) -> list[RouteMaster]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[RouteMaster]:
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
