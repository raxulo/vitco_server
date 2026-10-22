from fastapi import UploadFile
from pydantic import field_validator
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, model_validator
from app.core.validators import (
    apply_milk_quality_rules,
    apply_sample_rules,
    apply_shift_time_rules,
    digits_only,
    limit_at_most,
    min_not_above_max,
    mobile_number,
    sample_code,
)

# FAT / SNF limit fields: 2 digits, "." and 2 digits at most (99.99)
_LIMIT_FIELDS = (
    "cow_min_fat", "cow_max_fat", "cow_min_snf", "cow_max_snf",
    "buffalo_min_fat", "buffalo_max_fat", "buffalo_min_snf", "buffalo_max_snf",
    "min_fat", "max_fat", "min_snf", "max_snf",
)
from app.modules.mcc.domain.enums import MccType
from typing import Any

from app.modules.common.settings.domain.enums import (
    AnalyzerType,
    CattleType,
    CollectionMode,
    PrinterType,
    ReceiptSize,
    WeightUnit,
)


class CreateMccRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    mobile: str = Field(default=None, validate_default=True)  # missing -> "Mobile number is required"
    email: EmailStr

    @field_validator("code")
    @classmethod
    def _code_digits(cls, value: str) -> str:
        return digits_only(value, "MCC code")

    @field_validator("mobile", mode="before")
    @classmethod
    def _mobile_digits(cls, value: str) -> str:
        return mobile_number(value)

    password: str | None = None
    mcc_type: MccType = Field(default=MccType.NORMAL)

    line: str | None = None
    pincode: str | None = None
    city: str | None = None
    state: str | None = None

    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    route_code: int | None = None
    sample_start: int |None = 0
    sample_end: int |None = 0
    is_active: bool | None = True
    profile_image: UploadFile | None = None

    # Settings Config
    analyzer_type: AnalyzerType | None = AnalyzerType.TYPE_A
    analyzer_collection_mode: CollectionMode | None = CollectionMode.MANUAL
    weight_unit: WeightUnit | None = WeightUnit.LITER
    weight_collection_mode: CollectionMode | None = CollectionMode.MANUAL
    auto_tare_enabled: bool | None = False
    morning_collection_start: str | None = "06:00"
    morning_collection_end: str | None = "10:00"
    evening_collection_start: str | None = "12:00"
    evening_collection_end: str | None = "22:00"
    receipt_size: ReceiptSize | None = ReceiptSize.SMALL
    printer_type: PrinterType | None = PrinterType.NONE
    printer_enabled: bool | None = False
    cattle_type: CattleType | None = CattleType.COW_AND_BUFFALO
    max_rate_chart_count: int | None = 5
    settings_edit_enabled: bool | None = False
    rate_chart_edit_enabled: bool | None = False
    master_enabled: bool | None = False

    # Milk Quality Config
    cow_min_fat: float | None = Field(default=0.0, ge=0)
    cow_max_fat: float | None = Field(default=0.0, ge=0)
    cow_min_snf: float | None = Field(default=0.0, ge=0)
    cow_max_snf: float | None = Field(default=0.0, ge=0)
    buffalo_min_fat: float | None = Field(default=0.0, ge=0)
    buffalo_max_fat: float | None = Field(default=0.0, ge=0)
    buffalo_min_snf: float | None = Field(default=0.0, ge=0)
    buffalo_max_snf: float | None = Field(default=0.0, ge=0)

    # Fixed Rate Config
    fixed_rate: float | None = Field(default=0.0, ge=0)
    less_detection: float | None = Field(default=0.0, ge=0)
    high_detection: float | None = Field(default=0.0, ge=0)
    min_fat: float | None = Field(default=0.0, ge=0)
    max_fat: float | None = Field(default=0.0, ge=0)
    min_snf: float | None = Field(default=0.0, ge=0)
    max_snf: float | None = Field(default=0.0, ge=0)

    @field_validator("sample_start", mode="before")
    @classmethod
    def _sample_start_digits(cls, value):
        return sample_code(value, "Sample start code")

    @field_validator("sample_end", mode="before")
    @classmethod
    def _sample_end_digits(cls, value):
        return sample_code(value, "Sample end code")

    @model_validator(mode="after")
    def _quality_rules(self):
        apply_sample_rules(self, MccType.WEIGHT)
        limit_at_most(self, _LIMIT_FIELDS)
        apply_milk_quality_rules(self)
        min_not_above_max(self.min_fat, self.max_fat, "Fixed rate FAT")
        min_not_above_max(self.min_snf, self.max_snf, "Fixed rate SNF")
        apply_shift_time_rules(self)
        return self

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        # Any password is accepted (any case, length or characters)
        return value

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


class UpdateMccRequest(BaseModel):
    # Code is read-only after creation (older codes may contain letters), so it is not re-validated
    code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    mobile: str = Field(default=None, validate_default=True)  # missing -> "Mobile number is required"
    email: EmailStr

    @field_validator("mobile", mode="before")
    @classmethod
    def _mobile_digits(cls, value: str) -> str:
        return mobile_number(value)

    password: str | None = None
    mcc_type: MccType = Field(default=MccType.NORMAL)

    line: str | None = None
    pincode: str | None = None
    city: str | None = None
    state: str | None = None

    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    route_code: int | None = None
    sample_start: int |None = 0
    sample_end: int |None = 0
    is_active: bool | None = True
    profile_image: UploadFile | None = None

    # Settings Config
    analyzer_type: AnalyzerType | None = AnalyzerType.TYPE_A
    analyzer_collection_mode: CollectionMode | None = CollectionMode.MANUAL
    weight_unit: WeightUnit | None = WeightUnit.LITER
    weight_collection_mode: CollectionMode | None = CollectionMode.MANUAL
    auto_tare_enabled: bool | None = False
    morning_collection_start: str | None = "06:00"
    morning_collection_end: str | None = "10:00"
    evening_collection_start: str | None = "12:00"
    evening_collection_end: str | None = "22:00"
    receipt_size: ReceiptSize | None = ReceiptSize.SMALL
    printer_type: PrinterType | None = PrinterType.NONE
    printer_enabled: bool | None = False
    cattle_type: CattleType | None = CattleType.COW_AND_BUFFALO
    max_rate_chart_count: int | None = 5
    settings_edit_enabled: bool | None = False
    rate_chart_edit_enabled: bool | None = False
    master_enabled: bool | None = False

    # Milk Quality Config
    cow_min_fat: float | None = Field(default=0.0, ge=0)
    cow_max_fat: float | None = Field(default=0.0, ge=0)
    cow_min_snf: float | None = Field(default=0.0, ge=0)
    cow_max_snf: float | None = Field(default=0.0, ge=0)
    buffalo_min_fat: float | None = Field(default=0.0, ge=0)
    buffalo_max_fat: float | None = Field(default=0.0, ge=0)
    buffalo_min_snf: float | None = Field(default=0.0, ge=0)
    buffalo_max_snf: float | None = Field(default=0.0, ge=0)

    # Fixed Rate Config
    fixed_rate: float | None = Field(default=0.0, ge=0)
    less_detection: float | None = Field(default=0.0, ge=0)
    high_detection: float | None = Field(default=0.0, ge=0)
    min_fat: float | None = Field(default=0.0, ge=0)
    max_fat: float | None = Field(default=0.0, ge=0)
    min_snf: float | None = Field(default=0.0, ge=0)
    max_snf: float | None = Field(default=0.0, ge=0)

    @field_validator("sample_start", mode="before")
    @classmethod
    def _sample_start_digits(cls, value):
        return sample_code(value, "Sample start code")

    @field_validator("sample_end", mode="before")
    @classmethod
    def _sample_end_digits(cls, value):
        return sample_code(value, "Sample end code")

    @model_validator(mode="after")
    def _quality_rules(self):
        apply_sample_rules(self, MccType.WEIGHT)
        limit_at_most(self, _LIMIT_FIELDS)
        apply_milk_quality_rules(self)
        min_not_above_max(self.min_fat, self.max_fat, "Fixed rate FAT")
        min_not_above_max(self.min_snf, self.max_snf, "Fixed rate SNF")
        apply_shift_time_rules(self)
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