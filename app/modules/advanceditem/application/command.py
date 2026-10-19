from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class AdvanceItemCommand:
    item_master_id: UUID
    quantity: Decimal


@dataclass(slots=True, frozen=True)
class CreateAdvanceCommand:
    user_id: UUID
    advance_date: datetime
    created_by: UUID
    items: tuple[AdvanceItemCommand, ...]
    notes: str | None = None

@dataclass(slots=True, frozen=True)
class AdvanceListQuery:
    owner: CurrentUser
    page: int = 1
    size: int = 10

@dataclass(frozen=True, slots=True)
class AdvanceItemDetailDTO:

    id: UUID
    item_master_id: UUID
    item_name: str
    item_code: str
    quantity: Decimal
    unit_rate: Decimal
    amount: Decimal


@dataclass(frozen=True, slots=True)
class AdvanceDetailDTO:

    id: UUID
    user_id: UUID
    user_name: str
    user_role: Role
    advance_date: datetime
    created_by: UUID
    created_by_name: str
    created_by_role: Role
    notes: str | None
    total_amount: Decimal
    items: tuple[AdvanceItemDetailDTO, ...]    

@dataclass(frozen=True, slots=True)
class AdvanceListDTO:

    id: UUID
    user_id: UUID
    user_name: str
    user_role: Role
    advance_date: datetime
    created_by: UUID
    created_by_name: str
    created_by_role: Role
    notes: str | None
    total_amount: Decimal

@dataclass(frozen=True, slots=True)
class AdvanceListResponseDTO:

    items: list[AdvanceListDTO]
    page: int
    size: int
    total_page: int