from app.core.clock import now_naive_ist
from uuid import uuid4
from app.modules.farmer.application.command import CreateFarmer
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.farmer.domain.enums import MilkType


@dataclass(slots=True, frozen=True)
class Farmer:
    id: UUID
    user_id: UUID
    farmer_code: str
    vlcc_id: UUID | None
    address_id: UUID | None
    bank_account_id: UUID | None
    assigned_chart_rank: int

    milk_type: MilkType
    profile_image: str | None
    sms_enabled: bool
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime | None
    name: str | None = None
    mobile: str | None = None
    vlcc_name: str | None = None
    can_modify: bool = False
    is_deleted: bool = False
    deleted_at: datetime | None = None
    deleted_by: UUID | None = None

    @classmethod
    def create(cls, command: CreateFarmer):
        now = now_naive_ist()
        return cls(
            id=uuid4(),
            user_id=command.user_id,
            farmer_code=command.farmer_code,
            vlcc_id=command.vlcc_id,
            address_id=command.address_id,
            bank_account_id=command.bank_account_id,
            assigned_chart_rank=command.assigned_chart_rank if command.assigned_chart_rank is not None else 1,
            milk_type=command.milk_type,
            profile_image=command.profile_image,
            sms_enabled=command.sms_enabled,
            is_active=command.is_active,
            created_by=command.created_by,
            created_at=now,
            updated_at=now,
        )


@dataclass(slots=True, frozen=True)
class FarmerRelations:
    id: UUID
    user_id: UUID
    address_id: UUID | None
    bank_account_id: UUID | None
    assigned_chart_rank: int