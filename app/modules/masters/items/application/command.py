from app.middleware.authentication import CurrentUser

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class CreateItemMasterCommand:

    item_code: int
    item_name: str
    unit_id: UUID
    rate: Decimal
    created_by: UUID | None = None


@dataclass(slots=True)
class UpdateItemMasterCommand:

    id: UUID
    item_code: int
    item_name: str
    unit_id: UUID
    rate: Decimal
    is_active: bool
    owner: CurrentUser | None = None


@dataclass(slots=True)
class DeleteItemMasterCommand:

    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class GetItemMasterQuery:

    id: UUID
    owner: CurrentUser


@dataclass(slots=True)
class ListItemMasterQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None
    owner: CurrentUser | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
