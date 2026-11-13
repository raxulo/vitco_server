from app.modules.administration.application.command import PartialUserUpdateCommand
from fastapi import UploadFile
from app.middleware.authentication import CurrentUser
from app.modules.common.fixedrate_config.application.command import CreateFixedRateConfigCommand
from app.modules.common.settings.application.dto import CreateSettingsCommand
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.common.milk_quality.application.command import CreateMilkQualityConfigCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand
from dataclasses import dataclass

from uuid import UUID

from app.modules.mcc.domain.enums import MccType


@dataclass(slots=True)
class CreateMccCommand:

    code: str

    name: str

    email: str

    password: str

    mcc_type: MccType

    mobile: str | None = None

    route_code: int | None = None

    sample_start: int = 0

    sample_end: int = 0

    is_active: bool = True

    profile_image: UploadFile | None = None

    created_by: UUID | None = None

    visible_member: bool = True

    shift_delay: str = "00:00"


@dataclass(slots=True)
class UpdateMccCommand:

    id: UUID

    code: str

    name: str

    email: str

    mcc_type: MccType

    sample_start: int

    sample_end: int

    updated_by: UUID

    is_active: bool = True

    profile_image: str | None = None
    
    mobile: str | None = None

    route_code: int | None = None

    password: str | None = None

    # None keeps the stored value
    visible_member: bool | None = None

    # None keeps the stored value
    shift_delay: str | None = None



@dataclass(slots=True)
class DeleteMccCommand:

    id: UUID

    deleted_by: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class GetMccQuery:

    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True)
class ListMccQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None
    owner: CurrentUser | None = None
    # Optional filter: only MCCs in this Admin / Sub Admin's line (on top of the owner's scope)
    manager: CurrentUser | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


from app.modules.common.device_item_version.application.command import DeviceItemVersionInput

@dataclass(slots=True)
class CreateFullDetailMcc:
    mcc: CreateMccCommand | None = None
    bank_account: CreateBankAccountCommand | None = None
    milk_quality_config: CreateMilkQualityConfigCommand | None = None
    address: CreateAddressCommand | None = None
    setting: CreateSettingsCommand | None = None
    fixed_rate_config: CreateFixedRateConfigCommand | None = None
    created_by: UUID | None = None
    device_item_versions: list[DeviceItemVersionInput] | None = None


from app.modules.common.address.application.command import AddressData
from app.modules.common.bank.application.command import BankAccountData
from app.modules.administration.application.command import UserData
from app.modules.common.settings.application.dto import SettingsData

@dataclass(slots=True)
class UpdateFullDetailMcc:
    mcc: UpdateMccCommand
    user: UserData
    bank_account: BankAccountData | None = None
    milk_quality_config: CreateMilkQualityConfigCommand | None = None
    address: AddressData | None = None
    setting: SettingsData | None = None
    fixed_rate_config: CreateFixedRateConfigCommand | None = None
    updated_by: UUID | None = None
    device_item_versions: list[DeviceItemVersionInput] | None = None


from typing import Any
from app.modules.common.milk_quality.application.command import UpdateMilkQualityConfigCommand
from app.modules.common.fixedrate_config.application.command import UpdateFixedRateConfigCommand

@dataclass(slots=True, kw_only=True)
class PartialUpdateMccUser:
    name: str | None = None
    email: str | None = None
    mobile: str | None = None
    profile_image: Any | None = None


@dataclass(slots=True, kw_only=True)
class PartialUpdateFullDetailMcc:
    updated_by: UUID | None = None
    user: PartialUserUpdateCommand | Any | None = None
    bank_account: BankAccountData | None = None
    milk_quality_config: UpdateMilkQualityConfigCommand | None = None
    address: AddressData | None = None
    setting: SettingsData | None = None
    fixed_rate_config: UpdateFixedRateConfigCommand | CreateFixedRateConfigCommand | None = None
    device_item_versions: list[DeviceItemVersionInput] | None = None
