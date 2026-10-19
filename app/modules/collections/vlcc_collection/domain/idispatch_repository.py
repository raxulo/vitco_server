from datetime import datetime
from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.collections.vlcc_collection.domain.dispatch_entities import Dispatch


class IDispatchRepository(ABC):

    @abstractmethod
    async def create(self, dispatch: Dispatch) -> None:
        pass

    @abstractmethod
    async def get(self, id: UUID) -> Dispatch | None:
        pass

    @abstractmethod
    async def update(self, dispatch: Dispatch) -> None:
        pass

    @abstractmethod
    async def delete(self, id: UUID) -> None:
        pass

    @abstractmethod
    async def list(
        self,
        vlcc_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 1,
        size: int = 20,
    ) -> list[tuple[Dispatch, str]]:
        pass

    @abstractmethod
    async def count(
        self,
        vlcc_id: UUID | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        pass
