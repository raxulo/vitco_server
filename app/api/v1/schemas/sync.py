from app.modules.vlcc.domain.enums import VlccType
from app.modules.administration.presentation.requests import PartialUpdateUserRequest
from pydantic import BaseModel
from app.modules.common.address.presentation.requests import UpdateAddressRequest
from app.modules.common.bank.presentation.requests import UpdateBankAccountRequest
from app.modules.vlcc.presentation.requests import PartialUpdateVlccUserRequest
from app.modules.common.fixedrate_config.presentation.requests import UpdateFixedRateConfigRequest
from app.modules.common.milk_quality.presentation.requests import UpdateMilkQualityConfigRequest
from app.modules.common.settings.presentation.requests import UpdateSettingsRequest
from typing import Any
from app.modules.common.fixedrate_config.presentation.response import FixedRateConfigResponse
from app.modules.common.milk_quality.presentation.response import MilkQualityConfigResponse
from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.mcc.domain.enums import MccType
from app.modules.common.settings.domain.enums import CollectionMode
from app.modules.administration.domain.enums import Role
from app.modules.common.bank.domain.dto import BankAccountDto
from app.modules.common.address.application.dto import AddressDto
from app.modules.farmer.domain.enums import MilkType
from dataclasses import dataclass
from uuid import UUID

@dataclass(slots=True, kw_only=True)
class SubUserProfileSyncDto:
    id: UUID
    user_id: UUID
    code: str
    name: str
    email: str
    role: Role
    mobile: str | None
    profile_image: str | None
    uic_code: str | None
    milk_type: MilkType | None
    assigned_chart_rank: int = 1
    can_modify: bool = False
    address: AddressDto | None = None
    bank_account: BankAccountDto | None = None
    status: bool = True

@dataclass(slots=True, kw_only=True)
class VlccSettingSyncDto:
    config: SettingsResponse | None
    milk_quality_config: MilkQualityConfigResponse

@dataclass(slots=True, kw_only=True)
class MccSettingSyncDto:
    config: SettingsResponse | None
    milk_quality_config: MilkQualityConfigResponse
    fixed_rate_config: FixedRateConfigResponse

@dataclass(slots=True, kw_only=True)
class OwnerSyncDto:
    id: UUID | None
    name: str
    mobile: str | None
    email: str
    role: Role
    code: str | None
    mcc_type: MccType | None
    profile_image: str | None

@dataclass(slots=True, kw_only=True)
class VlccExtraInfoSyncDto:
    entry_mode: CollectionMode
    soc_percentage: float
    farmer_enabled: bool
    vlcc_type: VlccType = VlccType.NORMAL

@dataclass(slots=True, kw_only=True)
class MccExtraInfoSyncDto:
    mcc_type: MccType
    sample_start: int | None
    sample_end: int | None
    # False: the app must not show VLCC names (always True unless FAT / SNF or Fixed Rate)
    visible_member: bool = True
    # "HH:MM" the app takes off the clock when it records a collection (DECISION-029)
    shift_delay: str = "00:00"

@dataclass(slots=True, kw_only=True)
class FarmerExtraInfoSyncDto:
    sms_enabled: bool
    milk_type: MilkType
    assigned_chart_rank: int = 1


@dataclass(slots=True, kw_only=True)
class ProfileSyncDto:
    id: UUID
    user_id: UUID
    name: str
    email: str
    mobile: str | None
    code: str
    role: Role
    profile_image: str | None = None
    uic_code: str | None = None
    owner: OwnerSyncDto | None = None
    route_code: str | None = None
    route_name: str | None = None
    address: AddressDto | None = None
    bank_account: BankAccountDto | None = None


@dataclass(slots=True, kw_only=True)
class VlccSyncDto:
    status: bool
    role: Role
    profile: ProfileSyncDto
    sub_users: list[SubUserProfileSyncDto]
    vlcc_info: VlccExtraInfoSyncDto
    settings: VlccSettingSyncDto
    rate_charts: list[Any]

@dataclass(slots=True, kw_only=True)
class MccSyncDto:
    status: bool
    role: Role
    profile: ProfileSyncDto
    mcc_info: MccExtraInfoSyncDto
    settings: MccSettingSyncDto
    rate_charts: list[Any]
    sub_users: list[SubUserProfileSyncDto]

@dataclass(slots=True, kw_only=True)
class FarmerSyncDto:
    status: bool
    role: Role
    profile: ProfileSyncDto
    farmer_info: FarmerExtraInfoSyncDto

class UpdateSettingsConfigRequestPayload(UpdateSettingsRequest):
    id: str | None
    def model_dump(self, *, exclude_unset=False, **kwds):
        if 'exclude' not in kwds:
            kwds['exclude'] = {'role', 'id'}
        elif isinstance(kwds['exclude'], (str, int)):
            kwds['exclude'] = {kwds['exclude']}
        elif isinstance(kwds['exclude'], dict):
            pass
        
        return super().model_dump(**kwds)
        

class UpdateMilkQualityConfigRequestPayload(UpdateMilkQualityConfigRequest):
    id: str | None

    def model_dump(self, *, exclude_unset=False, **kwds):
        if 'exclude' not in kwds:
            kwds['exclude'] = {'id'}
        elif isinstance(kwds['exclude'], (str, int)):
            kwds['exclude'] = {kwds['exclude']}
        elif isinstance(kwds['exclude'], dict):
            pass
        
        return super().model_dump(**kwds)


class UpdateFixedRateConfigRequestPayload(UpdateFixedRateConfigRequest):
    id: str | None = None

    def model_dump(self, *, exclude_unset=False, **kwds):
        if 'exclude' not in kwds:
            kwds['exclude'] = {'id'}
        elif isinstance(kwds['exclude'], (str, int)):
            kwds['exclude'] = {kwds['exclude']}
        elif isinstance(kwds['exclude'], dict):
            pass
        
        return super().model_dump(**kwds)


class UpdateSettingsRequestPayload(UpdateSettingsRequest):
    config: UpdateSettingsRequest | None = None
    milk_quality_config: UpdateMilkQualityConfigRequestPayload | None = None
    fixed_rate_config: UpdateFixedRateConfigRequestPayload | None = None
    user: PartialUpdateVlccUserRequest | None = None
    bank_account: UpdateBankAccountRequest | None = None
    address: UpdateAddressRequest | None = None


class UpdateProfileRequestPayload(BaseModel):
    user: PartialUpdateUserRequest | None = None
    bank_account: UpdateBankAccountRequest | None = None
    address: UpdateAddressRequest | None = None

