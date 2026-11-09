from app.modules.mcc.domain.enums import MccType
from enum import Enum

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Mcc:

    id: UUID

    user_id: UUID

    code: str

    name: str

    mcc_type: MccType

    route_code: int | None

    sample_start: int | None

    sample_end: int | None

    address_id: UUID | None

    bank_account_id: UUID | None

    settings_id: UUID | None

    milk_quality_config_id: UUID | None

    fixed_rate_config_id: UUID | None

    profile_image: str | None

    is_active: bool

    created_by: UUID | None

    updated_by: UUID | None

    created_at: datetime

    updated_at: datetime | None

    is_deleted: bool = False

    deleted_at: datetime | None = None

    deleted_by: UUID | None = None

    can_modify: bool = False

    visible_member: bool = True


@dataclass(slots=True, frozen=True)
class MccRelations:
    id: UUID
    user_id: UUID
    address_id: UUID | None
    bank_account_id: UUID | None
    settings_id: UUID | None
    milk_quality_config_id: UUID | None
    fixed_rate_config_id: UUID | None