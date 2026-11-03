"""
Recycle Bin repository interface.

Python 3.13+
"""

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.recyclebin.domain.dto import DeletedRecordDto, PurgeScope
from app.modules.recyclebin.domain.enums import DeletedEntityType


class IRecycleBinRepository(ABC):

    @abstractmethod
    async def list_deleted(
        self,
        entity_type: DeletedEntityType,
        search: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[DeletedRecordDto], int]:
        """Soft-deleted records of one kind, newest deletion first, plus the total."""
        ...

    @abstractmethod
    async def get_deleted(
        self,
        entity_type: DeletedEntityType,
        record_id: UUID,
    ) -> tuple[DeletedRecordDto, UUID] | None:
        """The soft-deleted record and its user id, or None when it is not soft-deleted."""
        ...

    @abstractmethod
    async def resolve_scope(self, root_user_id: UUID) -> PurgeScope:
        """The root user plus its whole ownership tree (never a Super Admin)."""
        ...

    @abstractmethod
    async def count_impact(self, scope: PurgeScope) -> dict[str, int]:
        """Row counts the purge of `scope` removes."""
        ...

    @abstractmethod
    async def purge(self, scope: PurgeScope) -> None:
        """Permanently delete every row of `scope` and everything referencing it."""
        ...
