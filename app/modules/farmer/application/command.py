from app.modules.administration.application.command import PartialUserUpdateCommand
from app.modules.common.bank.application.command import BankAccountData
from app.modules.common.address.application.command import AddressData
from app.modules.administration.application.command import UserData
from app.modules.common.bank.application.command import UpdateBankAccountCommand
from app.modules.common.address.application.command import UpdateAddressCommand
from app.modules.administration.application.command import UpdateUserCommand
from app.modules.administration.application.command import CreateUserCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.common.address.application.command import CreateAddressCommand
from dataclasses import dataclass
from uuid import UUID

from app.modules.farmer.domain.enums import MilkType


@dataclass(slots=True, frozen=True)
class CreateFarmer:
    user_id: UUID
    farmer_code: str
    vlcc_id: UUID

    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    assigned_chart_rank: int = 1

    milk_type: MilkType = MilkType.MIXED
    profile_image: str | None = None

    sms_enabled: bool = False
    is_active: bool = True

    created_by: UUID | None = None


@dataclass(slots=True, kw_only=True)
class UpdateFarmer:
    id: UUID

    farmer_code: str | None = None
    vlcc_id: UUID | None = None
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    assigned_chart_rank: int | None = None

    milk_type: MilkType | None = None
    profile_image: str | None = None

    sms_enabled: bool | None = None
    is_active: bool | None = None
    updated_by: UUID | None = None

    def changes(self) -> dict:
        return {
            key: value
            for key, value in (
                ("farmer_code", self.farmer_code),
                ("vlcc_id", self.vlcc_id),
                ("address_id", self.address_id),
                ("bank_account_id", self.bank_account_id),
                ("assigned_chart_rank", self.assigned_chart_rank),
                ("milk_type", self.milk_type),
                ("sms_enabled", self.sms_enabled),
                ("is_active", self.is_active),
                ("updated_by", self.updated_by),
            )
        }


@dataclass(slots=True)
class CreateFarmerCommand:
    user_id: UUID
    farmer_code: str
    vlcc_id: UUID

    assigned_chart_rank: int = 1

    milk_type: MilkType = MilkType.MIXED
    profile_image: str | None = None

    sms_enabled: bool = False
    is_active: bool = True

    created_by: UUID | None = None    

@dataclass(slots=True, kw_only=True)
class UpdateFarmerCommand:
    id: UUID
    farmer_code: str
    vlcc_id: UUID

    assigned_chart_rank: int = 1

    milk_type: MilkType = MilkType.MIXED
    profile_image: str | None = None

    sms_enabled: bool = False
    is_active: bool = True

    updated_by: UUID | None = None 


@dataclass(slots=True)
class CreateFarmerDetailCommand:
    farmer: CreateFarmerCommand
    user: CreateUserCommand
    address: CreateAddressCommand
    bank_account: CreateBankAccountCommand

@dataclass(slots=True)
class UpdateFarmerDetailCommand:
    farmer: UpdateFarmerCommand
    user: UserData
    address: AddressData
    bank_account: BankAccountData
    owner: CurrentUser | None = None

from app.middleware.authentication import CurrentUser

@dataclass(slots=True, frozen=False)
class GetFarmerQuery:
    id: UUID
    owner: CurrentUser | None = None

@dataclass(slots=True, frozen=False)
class DeleteFarmerQuery:
    id: UUID
    owner: CurrentUser | None = None


@dataclass(slots=True, frozen=False)
class GetFarmerByCodeQuery:
    farmer_code: str
    owner: CurrentUser | None = None


@dataclass(slots=True, frozen=False)
class ListFarmerQuery:
    keyword: str | None = None
    vlcc_id: UUID | None = None
    owner: CurrentUser | None = None
    offset: int = 0
    limit: int = 10


@dataclass(slots=True)
class DeleteFarmerCommand:
    id: UUID
    deleted_by: UUID
    owner: CurrentUser | None = None


from typing import Any


@dataclass(slots=True, kw_only=True)
class PartialUpdateFullDetailFarmer:
    updated_by: UUID | None = None
    user: PartialUserUpdateCommand | Any | None = None
    bank_account: BankAccountData | None = None
    address: AddressData | None = None

        
