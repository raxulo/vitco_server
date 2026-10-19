"""
Advance Item / Advanced Master Pydantic Schemas

Validation & Response schemas for Advance Item API.

Python 3.13+
"""
from app.modules.administration.domain.enums import Role
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class AdvanceItemRequestItem(BaseModel):
    """Single item entry in Advance creation request."""
    item_master_id: UUID = Field(..., description="Item Master UUID")
    quantity: float = Field(..., gt=0.0, description="Item quantity (> 0)")


class CreateAdvanceItemRequest(BaseModel):
    """Request payload for issuing Advance Items to a counterparty user."""
    user_id: UUID = Field(..., description="Counterparty target User UUID")
    advance_date: Optional[datetime] = Field(None, description="Advance issue timestamp")
    items: List[AdvanceItemRequestItem] = Field(..., min_length=1, description="List of advance items")
    notes: Optional[str] = Field(None, description="Optional notes/remarks")


class AdvanceItemDetailSchema(BaseModel):
    """Detailed breakdown item within an Advance record."""
    id: str = Field(..., description="Advance Item UUID")
    item_master_id: str = Field(..., description="Item Master UUID")
    item_name: str = Field(..., description="Item name")
    item_code: str = Field(..., description="Item code")
    quantity: float = Field(..., description="Item quantity")
    unit_rate: float = Field(..., description="Unit rate at issue time")
    amount: float = Field(..., description="Total line amount")


class AdvanceSummarySchema(BaseModel):
    """Advance Record Summary."""
    id: str = Field(..., description="Advance Record UUID")
    user_id: str = Field(..., description="Recipient User UUID")
    user_name: str = Field(..., description="Recipient User Name")
    user_role: Optional[Role] = Field(None, description="Recipient User Role")
    advance_date: str = Field(..., description="Formatted advance issue date")
    created_by: str = Field(..., description="Issuer User UUID")
    created_by_name: str = Field(..., description="Issuer User Name")
    created_by_role: Optional[Role] = Field(None, description="Issuer User Role")
    notes: Optional[str] = Field(None, description="Notes")
    total_amount: float = Field(..., description="Total Advance Amount")
    items: Optional[List[AdvanceItemDetailSchema]] = Field(None, description="Detailed item items list (if detail endpoint)")


class AdvanceItemListResponse(BaseModel):
    """Standard paginated list response for Advance Items."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Advance items list fetched successfully", description="Response message")
    items: List[AdvanceSummarySchema] = Field(default_factory=list, description="Advance records list")
    limit: Optional[int] = Field(None, description="Items per page")
    offset: Optional[int] = Field(None, description="Offset")
    total: int = Field(0, description="Total matching items")
    pages: int = Field(1, description="Total pages")
    next_page: Optional[int] = Field(None, description="Next page number")
    has_more: bool = Field(False, description="Has more pages indicator")


class AdvanceItemSingleResponse(BaseModel):
    """Single advance record detail response wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Advance item operation successful", description="Response message")
    data: AdvanceSummarySchema = Field(..., description="Advance record detailed data")
