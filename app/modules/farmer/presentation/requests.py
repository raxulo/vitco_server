from fastapi import UploadFile
from typing import Any
from pydantic import field_validator, model_validator
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.core.validators import digits_only, mobile_number
from app.modules.farmer.domain.enums import MilkType


class CreateFarmerRequest(BaseModel):
    # User / Identity
    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    mobile: str = Field(default=None, validate_default=True)  # missing -> "Mobile number is required"
    # Any password is accepted (any case, length or characters)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("mobile", mode="before")
    @classmethod
    def _mobile_digits(cls, value: str | None) -> str:
        return mobile_number(value)
    
    # Farmer Specific
    farmer_code: str = Field(..., min_length=1, max_length=30)
    vlcc_id: UUID
    # R1..R15: the VLCC's n-th assigned rate chart
    assigned_chart_rank: int = Field(default=1, ge=1, le=15)

    @field_validator("farmer_code")
    @classmethod
    def _farmer_code_digits(cls, value: str) -> str:
        value = digits_only(value, "Farmer code")
        if len(value) > 6:
            raise ValueError("Farmer code can have at most 6 digits")
        return value
    milk_type: MilkType = Field(default=MilkType.MIXED)
    profile_image: UploadFile = None
    sms_enabled: bool = False
    is_active: bool = True

    # Address Details
    line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    # Bank Details
    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    @field_validator("assigned_chart_rank", mode="before")
    @classmethod
    def validate_assigned_chart_rank(cls, value: Any) -> int:
        if value == "" or value is None:
            return 1
        try:
            return int(value)
        except (ValueError, TypeError):
            return 1

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


class UpdateFarmerRequest(BaseModel):
    # User / Identity
    name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    mobile: str = Field(default=None, validate_default=True)  # missing -> "Mobile number is required"
    password: str | None = Field(None, min_length=1, max_length=128)

    @field_validator("mobile", mode="before")
    @classmethod
    def _mobile_digits(cls, value: str | None) -> str:
        return mobile_number(value)
    
    # Farmer Specific
    farmer_code: str = Field(..., min_length=1, max_length=30)
    vlcc_id: UUID
    assigned_chart_rank: int | None = None
    milk_type: MilkType = Field(default=MilkType.MIXED)
    profile_image: UploadFile = None
    sms_enabled: bool = False
    is_active: bool = True

    # Address Details
    line: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    # Bank Details
    bank_name: str | None = None
    account_holder: str | None = None
    account_number: str | None = None
    ifsc_code: str | None = None
    upi_id: str | None = None

    @field_validator("assigned_chart_rank", mode="before")
    @classmethod
    def validate_assigned_chart_rank(cls, value: Any) -> int | None:
        if value == "" or value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        if value == "" or value is None:
            return None
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