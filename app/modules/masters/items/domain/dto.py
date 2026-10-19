from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class ItemMasterDto:

    id: UUID
    item_code: int
    item_name: str
    unit_id: UUID
    rate: Decimal
    is_active: bool
    owner_name: str | None = None
    can_modify: bool = False


@dataclass(slots=True, frozen=True)
class ItemMasterListDto:

    id: UUID
    item_code: int
    item_name: str
    unit_id: UUID
    rate: Decimal
    is_active: bool
    owner_name: str | None = None
    can_modify: bool = False


@dataclass(slots=True, frozen=True)
class ItemMasterRateDto:

    id: UUID
    rate: Decimal