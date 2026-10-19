"""
VLCC API Schemas

Python 3.13+
"""
from pydantic import Field
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class VlccItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    vlcc_code: str
    uic_code: str
    name: str
    entry_mode: Any = None
    route_code: str | None = None
    is_active: bool
    assigned_chart_rank: int = 1
    owner_name: str | None = None
    profile_image: str | None = None
    analyzer_collection_mode: Any = None
    weight_collection_mode: Any = None
    can_modify: bool = False


class VlccListResponse(BaseModel):
    items: list[VlccItemResponse]
    page: int
    size: int
    total: int
    total_pages: int


class VlccDtoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
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
    entry_mode: Any = None
    route_code: str | None = None
    route_name: str | None = None
    soc_percentage: float = 0.0
    farmer_enabled: bool = True
    is_active: bool = True
    assigned_chart_rank: int = 1
    owner_name: str | None = None
    can_modify: bool = False


class VlccDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vlcc: VlccDtoResponse
    user: Any | None = None
    bank_account: Any | None = None
    address: Any | None = None
    setting: Any | None = None
    milk_quality_config: Any | None = None


class UpdateSettingsRequest(BaseModel):
    """Schema for updating operational settings."""
    analyzer_type: Any | None = Field(None, description="0=TYPE_A, 1=TYPE_B, 2=TYPE_C, 3=TYPE_D")
    analyzer_collection_mode: Any | None = Field(None, description="0=MANUAL, 1=AUTOMATIC")
    weight_unit: Any | None = Field(None, description="0=LITER, 1=KILOGRAM")
    weight_collection_mode: Any | None = Field(None, description="0=MANUAL, 1=AUTOMATIC")
    auto_tare_enabled: bool | None = None
    morning_collection_start: str | None = Field(None, description="e.g. '06:00'")
    morning_collection_end: str | None = Field(None, description="e.g. '10:00'")
    evening_collection_start: str | None = Field(None, description="e.g. '12:00'")
    evening_collection_end: str | None = Field(None, description="e.g. '22:00'")
    receipt_size: Any | None = Field(None, description="0=SMALL, 1=LARGE")
    printer_type: Any | None = Field(None, description="0=NONE, 1=THERMAL, 2=DOT_MATRIX, 3=LASER")
    printer_enabled: bool | None = None
    cattle_type: Any | None = Field(None, description="0=COW_AND_BUFFALO, 1=COW_ONLY, 2=BUFFALO_ONLY")
    max_rate_chart_count: int | None = None
    settings_edit_enabled: bool | None = None
    rate_chart_edit_enabled: bool | None = None
    master_enabled: bool | None = None


class UpdateVlccRequest(BaseModel):
    """Schema for updating VLCC details and settings."""
    name: str | None = None
    contact_person: str | None = None
    uic_code: str | None = None
    route_code: str | None = None
    soc_percentage: float | None = None
    farmer_enabled: bool | None = None
    is_active: bool | None = None
    settings: UpdateSettingsRequest | None = None
