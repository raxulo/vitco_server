from app.modules.administration.domain.entities import UserDto
from app.modules.common.address.application.dto import AddressDto
from app.modules.common.bank.domain.dto import BankAccountDto
from dataclasses import dataclass

from uuid import UUID

from app.modules.mcc.domain.enums import MccType


@dataclass(slots=True)
class MccDto:

    id: UUID

    user_id: UUID

    code: str

    name: str

    mcc_type: MccType

    route_code: int | None

    sample_start: int

    sample_end: int
    
    is_active: bool

    profile_image: str | None

    settings_id: UUID | None = None

    milk_quality_config_id: UUID | None = None

    fixed_rate_config_id: UUID | None = None
    can_modify: bool = False
    city: str | None = None


@dataclass(slots=True, frozen=True)
class MccListDto:
    id: UUID
    user_id: UUID
    code: str
    name: str
    mcc_type: MccType
    is_active: bool
    created_by_name: str | None
    profile_image: str | None
    user_name: str | None = None
    mobile: str | None = None
    email: str | None = None
    can_modify: bool = False
    city: str | None = None
    route_code: int | None = None


from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.common.milk_quality.presentation.response import MilkQualityConfigResponse
from app.modules.common.fixedrate_config.presentation.response import FixedRateConfigResponse


@dataclass(slots=True)
class MccDetailDto:
    user: UserDto
    mcc: MccDto
    bank_account: BankAccountDto | None
    address: AddressDto | None
    setting: SettingsResponse | None = None
    milk_quality_config: MilkQualityConfigResponse | None = None
    fixed_rate_config: FixedRateConfigResponse | None = None


