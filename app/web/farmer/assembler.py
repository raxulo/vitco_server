"""
Farmer Web ViewModel Assembler
"""

from uuid import UUID
from app.modules.administration.application.command import UserData, CreateUserCommand
from app.modules.common.address.application.command import AddressData, CreateAddressCommand
from app.modules.common.bank.application.command import BankAccountData, CreateBankAccountCommand
from app.modules.administration.domain.enums import Role
from app.modules.farmer.application.command import (
    CreateFarmerCommand,
    UpdateFarmerCommand,
    CreateFarmerDetailCommand,
    UpdateFarmerDetailCommand,
)
from app.modules.farmer.presentation.requests import CreateFarmerRequest, UpdateFarmerRequest


class FarmerAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        data: CreateFarmerRequest,
        created_by: UUID,
    ) -> CreateFarmerDetailCommand:

        has_address = any([data.line, data.city, data.state, data.pincode])
        has_bank = any([data.bank_name, data.account_holder, data.account_number, data.ifsc_code, data.upi_id])

        return CreateFarmerDetailCommand(
            user=CreateUserCommand(
                name=data.name,
                email=data.email,
                mobile=data.mobile,
                password_hash=data.password,
                role=Role.FARMER,
                is_active=data.is_active,
                created_by=created_by,
                profile_image=data.profile_image
            ),
            farmer=CreateFarmerCommand(
                user_id=None,  # Handled inside the handler after user creation
                farmer_code=data.farmer_code,
                vlcc_id=data.vlcc_id,
                assigned_chart_rank=getattr(data, "assigned_chart_rank", 1),
                milk_type=data.milk_type,
                profile_image=data.profile_image,
                sms_enabled=data.sms_enabled,
                is_active=data.is_active,
                created_by=created_by
            ),
            address=CreateAddressCommand(
                line=data.line,
                pincode=data.pincode,
                city=data.city,
                state=data.state,
            ) if has_address else None,
            bank_account=CreateBankAccountCommand(
                bank_name=data.bank_name,
                account_holder=data.account_holder,
                account_number=data.account_number,
                ifsc_code=data.ifsc_code,
                upi_id=data.upi_id,
            ) if has_bank else None,
        )

    @staticmethod
    def update(
        data: UpdateFarmerRequest,
        farmer_id: UUID,
        updated_by: UUID,
    ) -> UpdateFarmerDetailCommand:

        has_address = any([data.line, data.city, data.state, data.pincode])
        has_bank = any([data.bank_name, data.account_holder, data.account_number, data.ifsc_code, data.upi_id])

        return UpdateFarmerDetailCommand(
            farmer=UpdateFarmerCommand(
                id=farmer_id,
                farmer_code=data.farmer_code,
                vlcc_id=data.vlcc_id,
                assigned_chart_rank=getattr(data, "assigned_chart_rank", 1),
                milk_type=data.milk_type,
                profile_image=data.profile_image,
                sms_enabled=data.sms_enabled,
                is_active=data.is_active,
                updated_by=updated_by
            ),
            user=UserData(
                name=data.name,
                email=data.email,
                mobile=data.mobile,
                role=Role.FARMER,
                is_active=data.is_active,
                password_hash=data.password,
                profile_image=data.profile_image,
            ),
            address=AddressData(
                line=data.line,
                pincode=data.pincode,
                city=data.city,
                state=data.state,
            ) if has_address else None,
            bank_account=BankAccountData(
                bank_name=data.bank_name,
                account_holder=data.account_holder,
                account_number=data.account_number,
                ifsc_code=data.ifsc_code,
                upi_id=data.upi_id,
            ) if has_bank else None,
        )
