from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.vlcc.domain.enums import CollectionMode


@dataclass(slots=True)
class CreateVlccCommand:

    uic_code: str
    vlcc_code: str
    name: str
    email: str
    password: str
    contact_person: str | None = None
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    settings_id: UUID | None = None
    profile_image: str | None = None
    entry_mode: CollectionMode = CollectionMode.MANUAL
    route_code: int | None = None
    soc_percentage: float = 0.0
    farmer_enabled: bool = True
    created_by: UUID | None = None


@dataclass(slots=True)
class UpdateVlccCommand:

    id: UUID
    uic_code: str
    vlcc_code: str
    name: str
    email: str
    password: str | None
    contact_person: str | None
    address_id: UUID | None
    bank_account_id: UUID | None
    milk_quality_config_id: UUID | None
    settings_id: UUID | None
    profile_image: str | None
    entry_mode: CollectionMode
    route_code: int | None
    soc_percentage: float
    farmer_enabled: bool
    is_active: bool
    updated_by: UUID


@dataclass(slots=True)
class DeleteVlccCommand:

    id: UUID
    deleted_by: UUID


@dataclass(slots=True)
class GetVlccQuery:

    id: UUID


@dataclass(slots=True)
class ListVlccQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
