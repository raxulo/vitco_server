from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.collections.mcc_collection.domain.entities import MccCollection
from app.modules.collections.mcc_collection.domain.dto import (
    MccCollectionListDto,
    MccCollectionSummaryDto,
    MccDetailedCollectionDto,
)
from app.modules.collections.mcc_collection.domain.listing import CollectionTotals, MccCollectionFilters


class IMccCollectionRepository(ABC):


    @abstractmethod
    async def create(
        self,
        entity: MccCollection,
    ) -> None:
        ...

    @abstractmethod
    async def update(
        self,
        entity: MccCollection,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        id: UUID,
    ) -> None:
        ...

    @abstractmethod
    async def delete_bulk(
        self,
        ids: list[UUID],
        owner: Any,
    ) -> list[UUID]:
        ...


    @abstractmethod
    async def get_by_id(
        self,
        id: UUID,
    ) -> MccCollection | None:
        ...

    @abstractmethod
    async def list(
        self,
        offset: int,
        limit: int,
    ) -> list[MccCollectionListDto]:
        ...

    @abstractmethod
    async def search(
        self,
        keyword: str,
        offset: int,
        limit: int,
    ) -> list[MccCollectionListDto]:
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
    async def get_mcc_user_id(self, mcc_id: UUID) -> UUID | None:
        ...

    @abstractmethod
    async def totals(self, owner: Any, filters: MccCollectionFilters | None = None) -> CollectionTotals:
        ...

    @abstractmethod
    async def get_vlcc_user_id(self, vlcc_id:UUID) -> UUID | None:
        ...

    @abstractmethod
    async def get_collection_summary(
        self,
        date_from: datetime,
        date_to: datetime,
        owner: Any,
        shift: Any | None = None,
        exclude_zero_quality: bool = False,
    ) -> MccCollectionSummaryDto:
        ...

    @abstractmethod
    async def get_detailed_collection_list(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: Any | None = None,
        offset: int = 0,
        limit: int = 50,
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: Any | None = None,
        is_deleted: bool | None = None,
        exclude_zero_quality: bool = False,
    ) -> list[MccDetailedCollectionDto]:
        ...

    @abstractmethod
    async def get_total_collection_count(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        shift: Any | None = None,
        mcc_id: UUID | None = None,
        vlcc_id: UUID | None = None,
        owner: Any | None = None,
        is_deleted: bool | None = None,
        exclude_zero_quality: bool = False,
    ) -> int:
        ...

    @abstractmethod
    async def is_sample_number_collected(
        self,
        query: Any | None = None,
    ) -> bool:
        ...


