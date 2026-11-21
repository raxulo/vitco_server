"""
Login ViewModel Assembler
"""

from app.modules.mcc.presentation.requests import UpdateMccRequest
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.application.command import UpdateMccCommand
from app.modules.mcc.application.command import UpdateFullDetailMcc
from uuid import UUID
from app.modules.mcc.application.command import CreateMccCommand
from app.modules.common.bank.application.command import CreateBankAccountCommand
from app.modules.mcc.presentation.requests import CreateMccRequest
from app.modules.common.address.application.command import CreateAddressCommand
from app.modules.mcc.application.command import CreateFullDetailMcc
from app.modules.common.settings.application.dto import CreateSettingsCommand
from app.modules.common.milk_quality.application.command import CreateMilkQualityConfigCommand
from app.modules.common.fixedrate_config.application.command import CreateFixedRateConfigCommand
from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)



from app.modules.administration.application.command import UserData
from app.modules.common.address.application.command import AddressData
from app.modules.common.bank.application.command import BankAccountData
from app.modules.common.settings.application.dto import SettingsData
from app.modules.administration.domain.enums import Role


def _or_default(value, default):
    """`default` only when the field is missing: `value or default` would also
    replace a 0 choice (Liter, Cow & Buffalo, Printer None) with the default."""
    return default if value is None else value


class MccAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        form: CreateMccRequest,
        created_by: UUID,
    ) -> CreateFullDetailMcc:

        return CreateFullDetailMcc(
            created_by=created_by,
            mcc=CreateMccCommand(
                code= form.code,
                name= form.name,
                email= form.email,
                password= form.password,
                mcc_type= form.mcc_type,
                mobile= form.mobile,
                route_code= form.route_code,
                sample_start= form.sample_start,
                sample_end= form.sample_end,
                visible_member= form.visible_member or not form.mcc_type.supports_visible_member,
                shift_delay= form.shift_delay,
                is_active= form.is_active,
                created_by=created_by,
                profile_image=form.profile_image
            ), 
            address= CreateAddressCommand(
                line=form.line,
                pincode=form.pincode,
                city=form.city,
                state=form.state,
            ) if form.has_address else None,

            bank_account=CreateBankAccountCommand(
                bank_name=form.bank_name,
                account_holder=form.account_holder,
                account_number=form.account_number,
                ifsc_code=form.ifsc_code,
                upi_id=form.upi_id,
            ) if form.has_bank_details else None,

            setting=CreateSettingsCommand(
                analyzer_type=form.analyzer_type,
                analyzer_collection_mode=form.analyzer_collection_mode,
                weight_unit=form.weight_unit,
                weight_collection_mode=form.weight_collection_mode,
                auto_tare_enabled=form.auto_tare_enabled,
                morning_collection_start=form.morning_collection_start,
                morning_collection_end=form.morning_collection_end,
                evening_collection_start=form.evening_collection_start,
                evening_collection_end=form.evening_collection_end,
                receipt_size=form.receipt_size,
                printer_type=form.printer_type,
                printer_enabled=form.printer_enabled,
                cattle_type=form.cattle_type,
                max_rate_chart_count=form.max_rate_chart_count,
                settings_edit_enabled=form.settings_edit_enabled,
                rate_chart_edit_enabled=form.rate_chart_edit_enabled,
                master_enabled=getattr(form, "master_enabled", False) or False,
                created_by=created_by
            ),

            milk_quality_config=CreateMilkQualityConfigCommand(
                cow_min_fat=form.cow_min_fat or 0.0,
                cow_max_fat=form.cow_max_fat or 0.0,
                cow_min_snf=form.cow_min_snf or 0.0,
                cow_max_snf=form.cow_max_snf or 0.0,
                buffalo_min_fat=form.buffalo_min_fat or 0.0,
                buffalo_max_fat=form.buffalo_max_fat or 0.0,
                buffalo_min_snf=form.buffalo_min_snf or 0.0,
                buffalo_max_snf=form.buffalo_max_snf or 0.0,
            ) if form.mcc_type==MccType.NORMAL or form.mcc_type==MccType.FAT_SNF else None,
            fixed_rate_config=CreateFixedRateConfigCommand(
                fixed_rate=form.fixed_rate or 0.0,
                less_detection=form.less_detection or 0.0,
                high_detection=form.high_detection or 0.0,
                min_fat=form.min_fat or 0.0,
                max_fat=form.max_fat or 0.0,
                min_snf=form.min_snf or 0.0,
                max_snf=form.max_snf or 0.0,
            ) if form.mcc_type==MccType.FIXED_RATE else None,
        )

    @staticmethod
    def update(
        form: UpdateMccRequest,
        id: UUID,
        updated_by: UUID,
    ) -> UpdateFullDetailMcc:

        return UpdateFullDetailMcc(
            updated_by=updated_by,
            user=UserData(
                name=form.name,
                email=form.email,
                mobile=form.mobile,
                password_hash=form.password,
                is_active=form.is_active,
                role=Role.MCC,
                profile_image=form.profile_image
            ),
            mcc=UpdateMccCommand(
                id=id,
                updated_by=updated_by,
                code= form.code,
                name= form.name,
                email= form.email,
                password= form.password,
                mcc_type= form.mcc_type,
                mobile= form.mobile,
                route_code= form.route_code,
                sample_start= form.sample_start,
                sample_end= form.sample_end,
                visible_member= form.visible_member or not form.mcc_type.supports_visible_member,
                shift_delay= form.shift_delay,
                is_active= form.is_active,
            ),
            address= AddressData(
                line=form.line,
                pincode=form.pincode,
                city=form.city,
                state=form.state,
            ) if form.has_address else None,

            bank_account=BankAccountData(
                bank_name=form.bank_name,
                account_holder=form.account_holder,
                account_number=form.account_number,
                ifsc_code=form.ifsc_code,
                upi_id=form.upi_id,
            ) if form.has_bank_details else None,

            setting=SettingsData(
                analyzer_type=_or_default(form.analyzer_type, AnalyzerType.TYPE_A),
                analyzer_collection_mode=_or_default(form.analyzer_collection_mode, CollectionMode.MANUAL),
                weight_unit=_or_default(form.weight_unit, WeightUnit.KILOGRAM),
                weight_collection_mode=_or_default(form.weight_collection_mode, CollectionMode.MANUAL),
                auto_tare_enabled=form.auto_tare_enabled or False,
                morning_collection_start=form.morning_collection_start or "06:00",
                morning_collection_end=form.morning_collection_end or "13:00",
                evening_collection_start=form.evening_collection_start or "16:00",
                evening_collection_end=form.evening_collection_end or "21:00",
                receipt_size=_or_default(form.receipt_size, ReceiptSize.SMALL),
                printer_type=_or_default(form.printer_type, PrinterType.LASER),
                printer_enabled=form.printer_enabled or False,
                cattle_type=_or_default(form.cattle_type, CattleType.COW_ONLY),
                max_rate_chart_count=form.max_rate_chart_count or 5,
                settings_edit_enabled=form.settings_edit_enabled or False,
                rate_chart_edit_enabled=form.rate_chart_edit_enabled or False,
                master_enabled=getattr(form, "master_enabled", False) or False,
            ),

            milk_quality_config=CreateMilkQualityConfigCommand(
                cow_min_fat=form.cow_min_fat or 0.0,
                cow_max_fat=form.cow_max_fat or 0.0,
                cow_min_snf=form.cow_min_snf or 0.0,
                cow_max_snf=form.cow_max_snf or 0.0,
                buffalo_min_fat=form.buffalo_min_fat or 0.0,
                buffalo_max_fat=form.buffalo_max_fat or 0.0,
                buffalo_min_snf=form.buffalo_min_snf or 0.0,
                buffalo_max_snf=form.buffalo_max_snf or 0.0,
            ) if form.mcc_type==MccType.NORMAL or form.mcc_type==MccType.FAT_SNF else None,
            fixed_rate_config=CreateFixedRateConfigCommand(
                fixed_rate=form.fixed_rate or 0.0,
                less_detection=form.less_detection or 0.0,
                high_detection=form.high_detection or 0.0,
                min_fat=form.min_fat or 0.0,
                max_fat=form.max_fat or 0.0,
                min_snf=form.min_snf or 0.0,
                max_snf=form.max_snf or 0.0,
            ) if form.mcc_type==MccType.FIXED_RATE else None,
        )