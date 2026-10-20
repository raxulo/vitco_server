from fastapi import UploadFile
from typing import Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from app.core.validators import apply_milk_quality_rules, digits_only, mobile_number
from app.modules.vlcc.domain.enums import CollectionMode
from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode as SettingsCollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)


class CreateVlccRequest(BaseModel):
    # Identity
    uic_code: str = Field(..., min_length=1, max_length=50)
    vlcc_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    mobile: str
    password: str | None = None
    contact_person: str | None = Field(None, max_length=150)

    @field_validator("vlcc_code")
    @classmethod
    def _code_digits(cls, value: str) -> str:
        return digits_only(value, "VLCC code")

    @field_validator("mobile", mode="before")
    @classmethod
    def _mobile_digits(cls, value: str) -> str:
        return mobile_number(value)
    
    # Relationships/Ids
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    settings_id: UUID | None = None
    profile_image: UploadFile | None = None
    
    # VLCC Specific
    entry_mode: CollectionMode = Field(default=CollectionMode.MANUAL)
    route_code: int | None = None
    soc_percentage: float = Field(default=0.0, ge=0.0)
    farmer_enabled: bool = True
    assigned_chart_rank: int = Field(default=1, ge=1, le=15)
    is_active: bool = True

    # Address
    line: str | None = None
    pincode: str | None = None
    city: str | None = None
    state: str | None = None

    # Bank Account
    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    # Settings Config
    analyzer_type: AnalyzerType = AnalyzerType.TYPE_A
    analyzer_collection_mode: SettingsCollectionMode = SettingsCollectionMode.MANUAL
    weight_unit: WeightUnit = WeightUnit.LITER
    weight_collection_mode: SettingsCollectionMode = SettingsCollectionMode.MANUAL
    auto_tare_enabled: bool = False
    morning_collection_start: str = "06:00"
    morning_collection_end: str = "10:00"
    evening_collection_start: str = "12:00"
    evening_collection_end: str = "22:00"
    receipt_size: ReceiptSize = ReceiptSize.SMALL
    printer_type: PrinterType = PrinterType.NONE
    printer_enabled: bool = False
    cattle_type: CattleType = CattleType.COW_AND_BUFFALO
    max_rate_chart_count: int = 5
    settings_edit_enabled: bool = False
    rate_chart_edit_enabled: bool = False
    master_enabled: bool = False

    # Milk Quality Config
    cow_min_fat: float = Field(default=0.0, ge=0)
    cow_max_fat: float = Field(default=0.0, ge=0)
    cow_min_snf: float = Field(default=0.0, ge=0)
    cow_max_snf: float = Field(default=0.0, ge=0)
    buffalo_min_fat: float = Field(default=0.0, ge=0)
    buffalo_max_fat: float = Field(default=0.0, ge=0)
    buffalo_min_snf: float = Field(default=0.0, ge=0)
    buffalo_max_snf: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _milk_quality_rules(self):
        apply_milk_quality_rules(self)
        return self

    @model_validator(mode="before")
    @classmethod
    def empty_str_to_none(cls, data: any) -> any:
        if not isinstance(data, dict):
            try:
                data = dict(data)
            except (TypeError, ValueError):
                return data
        for key, value in list(data.items()):
            if value == "":
                data[key] = None
        return data

    @property
    def has_bank_details(self) -> bool:
        return self.account_holder is not None and any([
            self.bank_name,
            self.account_number,
            self.ifsc_code,
            self.upi_id,
        ])

    @property
    def has_address(self) -> bool:
        return any([
            self.line,
            self.city,
            self.state,
            self.pincode,
        ])


class UpdateVlccRequest(CreateVlccRequest):
    # Code is read-only after creation, so it is not re-validated on update
    @field_validator("vlcc_code")
    @classmethod
    def _code_digits(cls, value: str) -> str:
        return value


class PartialUpdateVlccUserRequest(BaseModel):
    name: str | None = Field(default=None)
    email: str | None = Field(default=None)
    mobile: str | None = Field(default=None)
    # profile_image: UploadFile | None = Field(default=None)