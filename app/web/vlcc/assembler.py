"""
VLCC Web ViewModel Assembler
"""

from app.modules.administration.application.command import UserData
from app.modules.common.address.application.command import AddressData
from app.modules.common.bank.application.command import BankAccountData
from app.modules.common.settings.application.dto import SettingsData
from app.modules.administration.domain.enums import Role
from app.modules.administration.application.command import CreateUserCommand
from uuid import UUID
from app.modules.vlcc.application.command import (
    CreateVlccCommand,
    UpdateVlccCommand,
    CreateFullDetailVlcc,
    UpdateFullDetailVlcc,
)
from app.modules.vlcc.presentation.requests import CreateVlccRequest
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.common.settings.application.dto import CreateSettingsCommand
from app.modules.common.milk_quality.application.command import CreateMilkQualityConfigCommand


class VlccAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        data: CreateVlccRequest,
        created_by: UUID,
    ) -> CreateFullDetailVlcc:

        return CreateFullDetailVlcc(
            created_by=created_by,
            user=CreateUserCommand(
                name=data.name,
                email=data.email,
                mobile=data.mobile,
                password_hash=data.password,
                role=Role.VLCC,
                is_active=True,
                created_by=created_by,
                profile_image=data.profile_image
            ),

            vlcc=CreateVlccCommand(
                uic_code=data.uic_code,
                vlcc_code=data.vlcc_code,
                name=data.name,
                contact_person=data.contact_person,
                entry_mode=data.entry_mode,
                route_code=data.route_code,
                soc_percentage=data.soc_percentage,
                farmer_enabled=data.farmer_enabled,
                assigned_chart_rank=data.assigned_chart_rank,
                created_by=created_by
            ), 
            address=CreateAddressCommand(
                line=data.line,
                pincode=data.pincode,
                city=data.city,
                state=data.state,
            ) if data.has_address else None,

            bank_account=CreateBankAccountCommand(
                bank_name=data.bank_name,
                account_holder=data.account_holder,
                account_number=data.account_number,
                ifsc_code=data.ifsc_code,
                upi_id=data.upi_id,
            ) if data.has_bank_details else None,

            setting=CreateSettingsCommand(
                analyzer_type=data.analyzer_type,
                analyzer_collection_mode=data.analyzer_collection_mode,
                weight_unit=data.weight_unit,
                weight_collection_mode=data.weight_collection_mode,
                auto_tare_enabled=data.auto_tare_enabled,
                morning_collection_start=data.morning_collection_start,
                morning_collection_end=data.morning_collection_end,
                evening_collection_start=data.evening_collection_start,
                evening_collection_end=data.evening_collection_end,
                receipt_size=data.receipt_size,
                printer_type=data.printer_type,
                printer_enabled=data.printer_enabled,
                cattle_type=data.cattle_type,
                max_rate_chart_count=data.max_rate_chart_count,
                settings_edit_enabled=data.settings_edit_enabled,
                rate_chart_edit_enabled=data.rate_chart_edit_enabled,
                master_enabled=getattr(data, "master_enabled", False) or False,
                created_by=created_by
            ),

            milk_quality_config=CreateMilkQualityConfigCommand(
                cow_min_fat=data.cow_min_fat,
                cow_max_fat=data.cow_max_fat,
                cow_min_snf=data.cow_min_snf,
                cow_max_snf=data.cow_max_snf,
                buffalo_min_fat=data.buffalo_min_fat,
                buffalo_max_fat=data.buffalo_max_fat,
                buffalo_min_snf=data.buffalo_min_snf,
                buffalo_max_snf=data.buffalo_max_snf,
            ),
        )

    @staticmethod
    def update(
        data: CreateVlccRequest,
        vlcc_id: UUID,
        updated_by: UUID,
    ) -> UpdateFullDetailVlcc:

        return UpdateFullDetailVlcc(
            updated_by=updated_by,
            user=UserData(
                name= data.name,
                email= data.email,
                mobile= data.mobile,
                password_hash= data.password,
                is_active= data.is_active,
                role=Role.VLCC,
                profile_image=data.profile_image
            ),
            vlcc=UpdateVlccCommand(
                id=vlcc_id,
                uic_code=data.uic_code,
                vlcc_code=data.vlcc_code,
                name=data.name,
                email=data.email,
                password_hash=data.password,
                contact_person=data.contact_person,
                entry_mode=data.entry_mode,
                route_code=data.route_code,
                soc_percentage=data.soc_percentage,
                farmer_enabled=data.farmer_enabled,
                is_active=data.is_active,
                assigned_chart_rank=data.assigned_chart_rank,
                updated_by=updated_by,
                address_id=data.address_id,
                bank_account_id=data.bank_account_id,
                milk_quality_config_id=data.milk_quality_config_id,
                settings_id=data.settings_id,
                profile_image=data.profile_image,
            ), 
            address=AddressData(
                line=data.line,
                pincode=data.pincode,
                city=data.city,
                state=data.state,
            ) if data.has_address else None,

            bank_account=BankAccountData(
                bank_name=data.bank_name,
                account_holder=data.account_holder,
                account_number=data.account_number,
                ifsc_code=data.ifsc_code,
                upi_id=data.upi_id,
            ) if data.has_bank_details else None,

            setting=SettingsData(
                analyzer_type=data.analyzer_type,
                analyzer_collection_mode=data.analyzer_collection_mode,
                weight_unit=data.weight_unit,
                weight_collection_mode=data.weight_collection_mode,
                auto_tare_enabled=data.auto_tare_enabled,
                morning_collection_start=data.morning_collection_start,
                morning_collection_end=data.morning_collection_end,
                evening_collection_start=data.evening_collection_start,
                evening_collection_end=data.evening_collection_end,
                receipt_size=data.receipt_size,
                printer_type=data.printer_type,
                printer_enabled=data.printer_enabled,
                cattle_type=data.cattle_type,
                max_rate_chart_count=data.max_rate_chart_count,
                settings_edit_enabled=data.settings_edit_enabled,
                rate_chart_edit_enabled=data.rate_chart_edit_enabled,
                master_enabled=getattr(data, "master_enabled", False) or False,
            ),

            milk_quality_config=CreateMilkQualityConfigCommand(
                cow_min_fat=data.cow_min_fat,
                cow_max_fat=data.cow_max_fat,
                cow_min_snf=data.cow_min_snf,
                cow_max_snf=data.cow_max_snf,
                buffalo_min_fat=data.buffalo_min_fat,
                buffalo_max_fat=data.buffalo_max_fat,
                buffalo_min_snf=data.buffalo_min_snf,
                buffalo_max_snf=data.buffalo_max_snf,
            ),
        )