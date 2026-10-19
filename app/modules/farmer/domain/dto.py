from app.modules.vlcc.domain.dto import VlccForFarmerDto
from app.modules.vlcc.domain.dto import VlccDto
from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.common.address.application.dto import AddressDto
from app.modules.common.bank.domain.dto import BankAccountDto
from app.modules.administration.domain.entities import UserDto
from dataclasses import dataclass
from uuid import UUID

from app.modules.farmer.domain.enums import MilkType


@dataclass(slots=True)
class FarmerDto:

    id: UUID
    user_id: UUID
    farmer_code: str
    name: str
    vlcc_id: UUID | None
    address_id: UUID | None
    bank_account_id: UUID | None
    milk_type: MilkType
    assigned_chart_rank: int = 1
    profile_image: str | None = None
    sms_enabled: bool = False
    is_active: bool = True
    vlcc_name: str | None = None
    can_modify: bool = False
    mobile: str | None = None


@dataclass(slots=True, frozen=True)
class FarmerListDto:
    id: UUID
    user_id: UUID
    farmer_code: str
    name: str
    milk_type: MilkType
    vlcc_id: UUID | None
    vlcc_name: str | None
    profile_image: str | None
    is_active: bool
    assigned_chart_rank: int = 1
    can_modify: bool = False
    mobile: str | None = None

@dataclass(slots=True)
class FarmerFullDetailDto:
    user: UserDto
    farmer: FarmerDto
    vlcc: VlccForFarmerDto | None
    bank_account: BankAccountDto | None
    address: AddressDto | None