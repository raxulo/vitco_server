"""
Unit Master Pydantic Schemas

Validation & Response schemas for Unit Master API.

Python 3.13+
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateUnitMasterRequest(BaseModel):
    """Request payload for creating a Unit Master."""
    name: str = Field(..., min_length=1, description="Unit name")


class UpdateUnitMasterRequest(BaseModel):
    """Request payload for updating a Unit Master."""
    name: str = Field(..., min_length=1, description="Unit name")
    is_active: bool = Field(True, description="Active status")


class UnitMasterSchema(BaseModel):
    """Unit Master record representation."""
    id: str = Field(..., description="Unit Master UUID")
    name: str = Field(..., description="Unit name")
    is_active: bool = Field(True, description="Active status")
    owner_name: Optional[str] = Field(None, description="Owner name")
    can_modify: bool = Field(True, description="Can modify indicator")


class UnitMasterListResponse(BaseModel):
    """Standard paginated list response for Unit Master."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Unit masters fetched successfully", description="Response message")
    items: List[UnitMasterSchema] = Field(default_factory=list, description="Unit master records")
    limit: Optional[int] = Field(None, description="Items per page")
    offset: Optional[int] = Field(None, description="Offset")
    total: int = Field(0, description="Total matching items")
    pages: int = Field(1, description="Total pages")
    next_page: Optional[int] = Field(None, description="Next page number")
    has_more: bool = Field(False, description="Has more pages indicator")


class UnitMasterSingleResponse(BaseModel):
    """Single unit response wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Unit master operation successful", description="Response message")
    data: UnitMasterSchema = Field(..., description="Unit master data")
