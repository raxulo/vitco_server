"""
Item Master Pydantic Schemas

Validation & Response schemas for Item Master API.

Python 3.13+
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CreateItemMasterRequest(BaseModel):
    """Request payload for creating an Item Master."""
    item_code: int = Field(..., gt=0, description="Unique item numeric code")
    item_name: str = Field(..., min_length=1, description="Item name")
    unit_id: UUID = Field(..., description="Measurement unit UUID")
    rate: float = Field(0.0, ge=0.0, description="Unit rate/price")


class UpdateItemMasterRequest(BaseModel):
    """Request payload for updating an Item Master."""
    item_code: int = Field(..., gt=0, description="Item numeric code")
    item_name: str = Field(..., min_length=1, description="Item name")
    unit_id: UUID = Field(..., description="Measurement unit UUID")
    rate: float = Field(0.0, ge=0.0, description="Unit rate/price")
    is_active: bool = Field(True, description="Active status")


class ItemMasterSchema(BaseModel):
    """Item Master record representation."""
    id: str = Field(..., description="Item Master UUID")
    item_code: int = Field(..., description="Item numeric code")
    item_name: str = Field(..., description="Item name")
    unit_id: str = Field(..., description="Unit UUID")
    rate: float = Field(..., description="Unit rate/price")
    is_active: bool = Field(True, description="Active status")
    owner_name: Optional[str] = Field(None, description="Owner name")
    can_modify: bool = Field(True, description="Can modify indicator")


class ItemMasterListResponse(BaseModel):
    """Standard paginated list response for Item Master."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Item masters fetched successfully", description="Response message")
    items: List[ItemMasterSchema] = Field(default_factory=list, description="Item master records")
    limit: Optional[int] = Field(None, description="Items per page")
    offset: Optional[int] = Field(None, description="Offset")
    total: int = Field(0, description="Total matching items")
    pages: int = Field(1, description="Total pages")
    next_page: Optional[int] = Field(None, description="Next page number")
    has_more: bool = Field(False, description="Has more pages indicator")


class ItemMasterSingleResponse(BaseModel):
    """Single item response wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Item master operation successful", description="Response message")
    data: ItemMasterSchema = Field(..., description="Item master data")
