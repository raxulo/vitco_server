from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID


@dataclass(slots=True)
class ItemMaster:

    id: UUID
    item_code: int
    item_name: str
    unit_id: UUID
    rate: Decimal
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None
    owner_name: str | None = None
    can_modify: bool = False
