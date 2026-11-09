"""
MCC API Schemas

Python 3.13+
"""
from __future__ import annotations

from typing import Any
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    QuantityCollectionMode,
)


class MccItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    code: str
    name: str
    mcc_type: Any
    is_active: bool
    created_by_name: str | None = None
    profile_image: str | None = None
    user_name: str | None = None
    mobile: str | None = None
    email: str | None = None
    can_modify: bool = False


class MccListResponse(BaseModel):
    items: list[MccItemResponse]
    page: int
    size: int
    total: int
    total_pages: int


class MccDtoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    code: str
    name: str
    mcc_type: Any
    route_code: int | None = None
    sample_start: int = 0
    sample_end: int = 0
    visible_member: bool = True
    is_active: bool
    profile_image: str | None = None
    settings_id: UUID | None = None
    milk_quality_config_id: UUID | None = None
    fixed_rate_config_id: UUID | None = None
    can_modify: bool = False


from app.api.v1.schemas.vlcc import UpdateSettingsRequest


class MccDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mcc: MccDtoResponse
    user: Any | None = None
    bank_account: Any | None = None
    address: Any | None = None
    setting: Any | None = None
    milk_quality_config: Any | None = None
    fixed_rate_config: Any | None = None


class UpdateMccRequest(BaseModel):
    """Schema for updating MCC details and settings."""
    name: str | None = None
    code: str | None = None
    mcc_type: Any | None = Field(None, description="0=NORMAL, 1=FAT_SNF, 2=WEIGHT, 3=FIXED_RATE")
    route_code: int | None = None
    sample_start: int | None = None
    sample_end: int | None = None
    is_active: bool | None = None
    settings: UpdateSettingsRequest | None = None


# =============================================================================
# Sample Number & Collection Query Schemas
# =============================================================================

class MccSampleResultResponse(BaseModel):
    """Response schema for MCC next sample number."""
    model_config = ConfigDict(from_attributes=True)

    sample_start: int
    sample_end: int
    is_mcc_exists: bool
    next_sample_number: int
    range: str | None = None
    out_of_range: bool | None = None
    is_ok: bool | None = None


class MccSampleCollectionDetail(BaseModel):
    """Detail schema for MCC milk collection queried by sample number."""
    model_config = ConfigDict(from_attributes=True)

    mcc_id: UUID
    mcc_name: str
    collection_id: UUID
    quantity: float
    can_count: int
    vlcc_id: UUID | None = None
    vlcc_name: str | None = None
    is_deleted: bool = False
    quantity_collection_mode: QuantityCollectionMode | int | None = None


class MccSampleInfo(BaseModel):
    """Info schema indicating status of collection query."""
    model_config = ConfigDict(from_attributes=True)

    mcc_id: UUID | None = None
    sample_number: int | None = None
    shift: Any | None = None
    collection_status: str | None = None
    status_code: int | None = None
    status: str | None = None


class MccCollectionBySampleResponse(BaseModel):
    """Response envelope for MCC milk collection queried by sample number."""
    model_config = ConfigDict(from_attributes=True)

    info: MccSampleInfo | None = None
    collection_detail: MccSampleCollectionDetail | None = None


class GetNextSampleNumberRequest(BaseModel):
    """Request schema for next sample number query."""
    shift: Any = Field(default=CollectionShift.MORNING, description="0=MORNING, 1=EVENING")
    collected_at: datetime | str | None = None


class GetCollectionBySampleNumberRequest(BaseModel):
    """Request schema for collection by sample number query."""
    sample_number: int
    shift: Any = Field(default=CollectionShift.MORNING, description="0=MORNING, 1=EVENING")
    collected_at: datetime | str | None = None


class CheckSampleNumberExistsResponse(BaseModel):
    """Response schema indicating whether a sample number is already collected."""
    mcc_id: UUID
    sample_number: int
    shift: Any
    is_collected: bool
    is_duplicate: bool
