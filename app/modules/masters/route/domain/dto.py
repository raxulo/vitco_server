from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class RouteMasterDto:

    id: UUID
    route_code: int
    route_name: str
    is_active: bool
    owner_name: str | None = None
    can_modify: bool = False


@dataclass(slots=True, frozen=True)
class RouteMasterListDto:

    id: UUID
    route_code: int
    route_name: str
    is_active: bool
    owner_name: str | None = None
    can_modify: bool = False
