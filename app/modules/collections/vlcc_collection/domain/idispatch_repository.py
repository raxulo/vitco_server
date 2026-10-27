from datetime import datetime
from abc import ABC, abstractmethod
from uuid import UUID

from app.middleware.authentication import CurrentUser
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.domain.dispatch_entities import Dispatch


class IDispatchRepository(ABC):

    @abstractmethod
    async def create(self, dispatch: Dispatch) -> None:
        pass

    @abstractmethod
    async def get(self, id: UUID, owner: CurrentUser) -> Dispatch | None:
        pass

    @abstractmethod
    async def vlcc_in_scope(self, vlcc_id: UUID, owner: CurrentUser) -> bool:
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
        owner: CurrentUser,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page: int = 1,
        size: int = 20,
    ) -> list[tuple[Dispatch, str]]:
        pass

    @abstractmethod
    async def count(
        self,
        owner: CurrentUser,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> int:
        pass

    @abstractmethod
    async def get_comparison(
        self,
        owner: CurrentUser,
        vlcc_id: UUID | None = None,
        shift: CollectionShift | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list, object]:
        pass

