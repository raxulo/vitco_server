"""
Recycle Bin commands and queries.

Python 3.13+
"""

from dataclasses import dataclass
from uuid import UUID

from app.middleware.authentication import CurrentUser
from app.modules.recyclebin.domain.enums import DeletedEntityType


@dataclass(slots=True, kw_only=True)
class ListDeletedRecordsQuery:
    entity_type: DeletedEntityType
    owner: CurrentUser
    search: str | None = None
    offset: int = 0
    limit: int = 20


@dataclass(slots=True, kw_only=True)
class GetPurgeImpactQuery:
    entity_type: DeletedEntityType
    record_id: UUID
    owner: CurrentUser


@dataclass(slots=True, kw_only=True)
class PurgeRecordCommand:
    entity_type: DeletedEntityType
    record_id: UUID
    owner: CurrentUser
