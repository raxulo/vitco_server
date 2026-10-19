from app.modules.common.address.application.command import AddressData
from app.modules.common.bank.application.command import BankAccountData
from app.modules.administration.application.command import UserData
from app.modules.common.settings.application.dto import SettingsData
from app.modules.common.settings.application.dto import UpdateSettingsCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.common.milk_quality.application.command import UpdateMilkQualityConfigCommand
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.administration.application.command import CreateUserCommand

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.vlcc.domain.enums import CollectionMode


# @dataclass(slots=True)
# class CreateVlccCommand:
#     uic_code: str
#     vlcc_code: str
#     name: str
#     email: str
#     password: str
#     mobile: str
#     contact_person: str | None = None
#     address_id: UUID | None = None
#     bank_account_id: UUID | None = None
#     milk_quality_config_id: UUID | None = None
#     settings_id: UUID | None = None
#     profile_image: str | None = None
#     entry_mode: CollectionMode | None = CollectionMode.MANUAL
#     route_code: int | None = None
#     soc_percentage: float = 0.0
#     farmer_enabled: bool = True
#     created_by: UUID | None = None

from dataclasses import dataclass
from uuid import UUID

from app.modules.vlcc.domain.enums import CollectionMode

@dataclass(frozen=True, slots=True, kw_only=True)
class CreateVlcc:
    user_id: UUID
    uic_code: str
    vlcc_code: str
    name: str

    contact_person: str | None = None
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    settings_id: UUID | None = None
    profile_image: str | None = None

    entry_mode: CollectionMode = CollectionMode.MANUAL
    route_code: str | None = None
    soc_percentage: float = 0.0
    farmer_enabled: bool = True
    is_active: bool = True
    assigned_chart_rank: int = 1
    created_by: UUID | None = None


@dataclass(slots=True, kw_only=True)
class VlccCommandBase:

    uic_code: str
    vlcc_code: str
    name: str
    contact_person: str | None = None
    profile_image: str | None = None
    entry_mode: CollectionMode = CollectionMode.MANUAL
    route_code: int | None = None
    soc_percentage: float = 0.0
    farmer_enabled: bool = True
    assigned_chart_rank: int = 1

@dataclass(slots=True, kw_only=True)
class CreateVlccCommand(VlccCommandBase):

    created_by: UUID | None = None

@dataclass(slots=True, kw_only=True)
class UpdateVlccCommand(VlccCommandBase):

    id: UUID
    updated_by: UUID
    email: str | None
    password_hash: str | None = None
    uic_code: str | None = None
    vlcc_code: str | None = None
    mobile: str | None = None
    is_active: bool = True
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    settings_id: UUID | None = None


@dataclass(slots=True)
class DeleteVlccCommand:

    id: UUID
    deleted_by: UUID
    owner: CurrentUser | None = None


from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.common.milk_quality.application.command import CreateMilkQualityConfigCommand
from app.modules.common.settings.application.dto import CreateSettingsCommand

@dataclass(slots=True)
class GetVlccQuery:

    id: UUID
    owner: CurrentUser | None = None


from app.middleware.authentication import CurrentUser

@dataclass(slots=True)
class ListVlccQuery:

    page: int = 1
    size: int = 20
    keyword: str | None = None
    owner: CurrentUser | None = None

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


from app.modules.common.device_item_version.application.command import DeviceItemVersionInput

@dataclass(slots=True)
class CreateFullDetailVlcc:
    vlcc: CreateVlccCommand
    user: CreateUserCommand
    bank_account: CreateBankAccountCommand | None = None
    milk_quality_config: CreateMilkQualityConfigCommand | None = None
    address: CreateAddressCommand | None = None
    setting: CreateSettingsCommand | None = None
    created_by: UUID | None = None
    device_item_versions: list[DeviceItemVersionInput] | None = None

@dataclass(slots=True)
class UpdateFullDetailVlcc:
    vlcc: UpdateVlccCommand
    user: UserData
    bank_account: BankAccountData | None = None
    milk_quality_config: UpdateMilkQualityConfigCommand | None = None
    address: AddressData | None = None
    setting: SettingsData | None = None
    updated_by: UUID | None = None
    device_item_versions: list[DeviceItemVersionInput] | None = None


from app.modules.administration.application.command import PartialUserUpdateCommand

@dataclass(slots=True, kw_only=True)
class PartialUpdateFullDetailVlcc:
    updated_by: UUID | None = None
    user: PartialUserUpdateCommand | None = None
    bank_account: BankAccountData | None = None
    milk_quality_config: UpdateMilkQualityConfigCommand | None = None
    address: AddressData | None = None
    setting: SettingsData | None = None
    device_item_versions: list[DeviceItemVersionInput] | None = None


