from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class RouteMaster:

    id: UUID
    route_code: int
    route_name: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None
    owner_name: str | None = None
    can_modify: bool = False
