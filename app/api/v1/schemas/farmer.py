"""
Farmer API Schemas

Python 3.13+
"""
from fastapi import UploadFile
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CheckCodeRequest(BaseModel):
    code: str | None = None
    farmer_code: str | None = None
    vlcc_id: UUID | None = None


class CheckCodeResponse(BaseModel):
    exists: bool
    available: bool
    farmer_code: str
    vlcc_id: str
    message: str


class CreateFarmerApiRequest(BaseModel):
    farmer_code: str = Field(..., min_length=1, max_length=30)
    name: str = Field(..., min_length=1, max_length=150)
    vlcc_id: UUID | None = None
    email: str | None = None
    mobile: str | None = None
    password: str | None = None

    assigned_chart_rank: int = 1
    milk_type: Any = 2  # 0=COW, 1=BUFFALO, 2=MIXED
    profile_image: UploadFile | None = None
    sms_enabled: bool = False
    is_active: bool = True

    @field_validator("assigned_chart_rank", mode="before")
    @classmethod
    def validate_chart_rank(cls, value: Any) -> int:
        if value is None or value == "":
            return 1
        try:
            return int(value)
        except (ValueError, TypeError):
            return 1

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


class UpdateFarmerApiRequest(BaseModel):
    farmer_code: str | None = None
    name: str | None = None
    vlcc_id: UUID | None = None
    email: str | None = None
    mobile: str | None = None
    password: str | None = None

    assigned_chart_rank: int | None = None
    milk_type: Any | None = None
    profile_image: str | None = None
    sms_enabled: bool | None = None
    is_active: bool | None = None

    @field_validator("assigned_chart_rank", mode="before")
    @classmethod
    def validate_chart_rank(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

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


class FarmerItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    farmer_code: str
    name: str
    milk_type: Any
    vlcc_id: UUID | None = None
    vlcc_name: str | None = None
    profile_image: str | None = None
    is_active: bool
    assigned_chart_rank: int = 1
    can_modify: bool = False
    mobile: str | None = None


class FarmerListResponse(BaseModel):
    status: bool = True
    code: int = 200
    message: str = "Farmers fetched successfully"
    items: list[FarmerItemResponse] = Field(default_factory=list)
    page: int = 1
    size: int = 20
    total: int = 0
    total_pages: int = 1
    limit: int | None = None
    offset: int | None = None
    pages: int = 1
    next_page: int | None = None
    has_more: bool = False


class FarmerDtoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: bool = True
    code: int = 200
    message: str = "Operation completed successfully"
    id: UUID | None = None
    user_id: UUID | None = None
    farmer_code: str | None = None
    name: str | None = None
    milk_type: Any | None = None
    vlcc_id: UUID | None = None
    vlcc_name: str | None = None
    address_id: UUID | None = None
    bank_account_id: UUID | None = None
    assigned_chart_rank: int = 1
    profile_image: str | None = None
    sms_enabled: bool = False
    is_active: bool = True
    can_modify: bool = False
    user: Any | None = None
    address: Any | None = None
    bank_account: Any | None = None
    data: Any | None = None


class DeleteFarmerResponse(BaseModel):
    status: bool = True
    code: int = 200
    message: str = "Member deleted successfully"
    farmer_id: UUID | None = None
    member_id: UUID | None = None

