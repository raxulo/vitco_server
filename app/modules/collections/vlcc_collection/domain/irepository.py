from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.collections.vlcc_collection.domain.entities import VlccCollection
from app.modules.collections.vlcc_collection.domain.dto import (
    VlccCollectionListDto,
    VlccCollectionSummaryDto,
    VlccDetailedCollectionDto,
)
from app.modules.collections.mcc_collection.domain.listing import CollectionTotals, VlccCollectionFilters
from app.middleware.authentication import CurrentUser


class IVlccCollectionRepository(ABC):


    @abstractmethod
    async def create(
        self,
        entity: VlccCollection,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: VlccCollection,
        owner: CurrentUser,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> None:
        ...

    @abstractmethod
    async def delete_bulk(
        self,
        ids: list[UUID],
        owner: CurrentUser,
    ) -> list[UUID]:
        ...


    @abstractmethod
    async def get_by_id(
        self,
        id: UUID,
        owner: CurrentUser,
    ) -> VlccCollection | None:
        ...

    @abstractmethod
    async def list(
        self,
        offset: int,
        limit: int,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[VlccCollectionListDto]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
        owner: CurrentUser,
    ) -> list[VlccCollectionListDto]:
        ...

    @abstractmethod
    async def count(
        self,
        owner: CurrentUser,
        keyword: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        ...

    @abstractmethod
    async def count_search(
        self,
        keyword: str,
        owner: CurrentUser,
    ) -> int:
        ...

    @abstractmethod
    async def totals(self, owner: CurrentUser, filters: VlccCollectionFilters | None = None) -> CollectionTotals:
        ...

    @abstractmethod
    async def count_export(self, owner: CurrentUser, filters: VlccCollectionFilters | None = None) -> int:
        ...

    @abstractmethod
    async def export_page(
        self,
        owner: CurrentUser,
        filters: VlccCollectionFilters | None,
        after: tuple[datetime, UUID] | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def get_vlcc_user_id(self, vlcc_id: UUID) -> UUID | None:
        ...

    @abstractmethod
    async def get_farmer_user_id(self, farmer_id: UUID) -> UUID | None:
        ...

    @abstractmethod
    async def get_collection_summary(
        self,
        date_from: datetime,
        date_to: datetime,
        owner: CurrentUser,
        shift: Any | None = None,
    ) -> VlccCollectionSummaryDto:
        ...

    @abstractmethod
    async def get_detailed_collection_list(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: Any | None = None,
        offset: int = 0,
        limit: int = 50,
        vlcc_id: UUID | None = None,
        farmer_id: UUID | None = None,
        owner: CurrentUser | None = None,
        is_deleted: bool | None = None,
    ) -> list[VlccDetailedCollectionDto]:
        ...





