"""
Recycle Bin DTOs.

Python 3.13+
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.modules.recyclebin.domain.enums import DeletedEntityType


@dataclass(slots=True, kw_only=True)
class DeletedRecordDto:
    """One row of a recycle bin tab."""

    id: UUID
    entity_type: DeletedEntityType
    code: str | None
    name: str
    email: str | None
    mobile: str | None
    parent_name: str | None
    deleted_at: datetime | None
    deleted_by_name: str | None
    deleted_by_id: UUID | None = None

    @property
    def deleted_by_label(self) -> str:
        """Who deleted it: the name, or why there is none."""
        if self.deleted_by_name:
            return self.deleted_by_name
        return "Removed account" if self.deleted_by_id else "Not recorded"


@dataclass(slots=True, kw_only=True)
class PurgeScope:
    """Every row id a purge removes, resolved from one soft-deleted root user."""

    root_user_id: UUID
    user_ids: set[UUID] = field(default_factory=set)
    mcc_ids: set[UUID] = field(default_factory=set)
    vlcc_ids: set[UUID] = field(default_factory=set)
    farmer_ids: set[UUID] = field(default_factory=set)


@dataclass(slots=True, kw_only=True)
class PurgeImpactDto:
    """What a purge will remove — shown before the user confirms."""

    entity_type: DeletedEntityType
    record_id: UUID
    name: str
    code: str | None
    confirm_text: str
    deleted_at: datetime | None = None
    deleted_by_label: str = "Not recorded"
    admins: int = 0
    sub_admins: int = 0
    mccs: int = 0
    vlccs: int = 0
    farmers: int = 0
    active_records: int = 0
    mcc_collections: int = 0
    vlcc_collections: int = 0
    dispatches: int = 0
    payment_transfers: int = 0
    rate_charts: int = 0
    advances: int = 0
    marketplace_listings: int = 0

    @property
    def descendants(self) -> int:
        """Users removed besides the record itself."""
        return self.admins + self.sub_admins + self.mccs + self.vlccs + self.farmers - 1
