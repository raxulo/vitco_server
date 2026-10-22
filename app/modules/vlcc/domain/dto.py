from dataclasses import dataclass
from uuid import UUID

from app.modules.vlcc.domain.enums import CollectionMode

from app.modules.administration.domain.entities import UserDto
from app.modules.common.address.application.dto import AddressDto
from app.modules.common.bank.domain.dto import BankAccountDto
from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.common.milk_quality.presentation.response import MilkQualityConfigResponse

@dataclass(slots=True)
class VlccDto:

    id: UUID
    user_id: UUID
    uic_code: str
    vlcc_code: str
    name: str
    contact_person: str | None
    address_id: UUID | None
    bank_account_id: UUID | None
    milk_quality_config_id: UUID | None
    settings_id: UUID | None
    profile_image: str | None
    entry_mode: CollectionMode
    route_code: str | None
    route_name: str | None
    soc_percentage: float
    farmer_enabled: bool
    is_active: bool
    assigned_chart_rank: int = 1
    owner_name: str | None = None
    can_modify: bool = False
    city: str | None = None
    mobile: str | None = None

@dataclass(slots=True, frozen=True)
class VlccListDto:
    id: UUID
    user_id: UUID
    vlcc_code: str
    uic_code: str
    name: str
    entry_mode: CollectionMode
    route_code: str | None
    is_active: bool
    assigned_chart_rank: int = 1
    owner_name: str | None = None
    profile_image: str | None = None
    analyzer_collection_mode: CollectionMode | None = None
    weight_collection_mode: CollectionMode | None = None
    can_modify: bool = False
    city: str | None = None

@dataclass(slots=True)
class VlccDetailDto:
    vlcc: VlccDto
    user: UserDto
    bank_account: BankAccountDto | None = None
    address: AddressDto | None = None
    setting: SettingsResponse | None = None
    milk_quality_config: MilkQualityConfigResponse | None = None



@dataclass(slots=True)
class VlccWithMccListDto:
    vlcc_id: UUID
    mcc_id: UUID
    vlcc_code: str
    vlcc_name: str
    assigned_rate_chart_id: UUID | None = None
    assigned_chart_rank: int = 1
    uic_code: str | None = None
    route_code: str | None = None
    mobile: str | None = None
    owner_name: str | None = None

@dataclass(slots=True)
class VlccForMccDto:
    vlcc_id: UUID
    vlcc_code: str
    vlcc_name: str
    email:str
    mobile:str
    entry_mode: CollectionMode
    profile_image: str | None
    route_code: str | None
    route_name: str | None
    uic_code: str | None = None
    assigned_chart_rank: int = 1

@dataclass(slots=True)
class VlccForFarmerDto:
    id: UUID
    code: str
    name: str
    email:str
    mobile:str
    profile_image: str | None
    uic_code: str | None = None

@dataclass(slots=True)
class VlccWithAllDetailsForMccDto:
    vlcc: VlccForMccDto
    address: AddressDto | None = None
    bank_account: BankAccountDto | None = None
    