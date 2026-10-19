from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True)
class UnitMasterDto:

    id: UUID
    name: str
    is_active: bool
    owner_name: str | None = None
    can_modify: bool = False


@dataclass(slots=True, frozen=True)
class UnitMasterListDto:

    id: UUID
    name: str
    is_active: bool
    owner_name: str | None = None
    can_modify: bool = False
