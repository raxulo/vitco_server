from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.vlcc.domain.entities import Vlcc
from app.middleware.authentication import CurrentUser


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

    @abstractmethod
    async def set_chart_rank_by_route(
        self,
        route_code: int,
        chart_rank: int,
        owner: CurrentUser,
    ) -> list[UUID]:
        """Set assigned_chart_rank on every VLCC on a route the owner can see; returns their user ids."""
        ...
