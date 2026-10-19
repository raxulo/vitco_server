"""
Dispatch Pydantic Schemas

Validation & Response schemas for Milk Dispatch API.

Python 3.13+
"""
from app.core.clock import to_naive_ist
from app.core.clock import now_naive_ist
from uuid import UUID
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MeasurementMode,
    QuantityCollectionMode,
)


class CreateDispatchRequest(BaseModel):
    """
    Request schema for recording a milk dispatch note.
    Contains strictly the requested domain fields.
    """
    collected_at: datetime = Field(..., description="Dispatch timestamp")
    shift: CollectionShift = Field(
        default=CollectionShift.MORNING,
        description="Collection shift (0: MORNING, 1: EVENING)",
    )
    fat_percent: float = Field(..., ge=0.0, le=100.0, description="FAT percentage")
    snf_percent: float = Field(..., ge=0.0, le=100.0, description="SNF percentage")
    quantity: float = Field(..., gt=0.0, description="Milk quantity in Litres/Kg")
    can_count: int = Field(..., ge=0, description="Number of milk cans")
    quantity_collection_mode: QuantityCollectionMode = Field(
        default=QuantityCollectionMode.MANUAL,
        description="Quantity collection mode (0: MANUAL, 1: AUTOMATIC)",
    )
    measurement_mode: MeasurementMode = Field(
        default=MeasurementMode.MANUAL,
        description="Measurement mode (0: MANUAL, 1: AUTOMATIC)",
    )

    def get_collected_at(self) -> datetime:
        return to_naive_ist(self.collected_at) if self.collected_at else now_naive_ist()


class UpdateDispatchRequest(BaseModel):
    """
    Request schema for updating an existing dispatch note.
    """
    collected_at: Optional[datetime] = Field(None, description="Dispatch timestamp")
    shift: Optional[CollectionShift] = Field(
        None,
        description="Collection shift (0: MORNING, 1: EVENING)",
    )
    fat_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="FAT percentage")
    snf_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="SNF percentage")
    quantity: Optional[float] = Field(None, gt=0.0, description="Milk quantity in Litres/Kg")
    can_count: Optional[int] = Field(None, ge=0, description="Number of milk cans")
    quantity_collection_mode: Optional[QuantityCollectionMode] = Field(
        None,
        description="Quantity collection mode (0: MANUAL, 1: AUTOMATIC)",
    )
    measurement_mode: Optional[MeasurementMode] = Field(
        None,
        description="Measurement mode (0: MANUAL, 1: AUTOMATIC)",
    )
    def get_collected_at(self) -> datetime:
        return to_naive_ist(self.collected_at) if self.collected_at else now_naive_ist()


class DispatchSchema(BaseModel):
    """Milk dispatch representation."""
    id: UUID = Field(..., description="Dispatch UUID")
    vlcc_id: UUID = Field(..., description="VLCC UUID")
    vlcc_name: Optional[str] = Field(None, description="VLCC center name")
    collected_at: datetime = Field(..., description="ISO datetime of collection")
    shift: CollectionShift = Field(CollectionShift.MORNING, description="Collection shift (0: MORNING, 1: EVENING)")
    fat_percent: float = Field(..., description="FAT percentage")
    snf_percent: float = Field(..., description="SNF percentage")
    quantity: float = Field(..., description="Quantity in Litres")
    can_count: int = Field(..., description="Number of cans")
    quantity_collection_mode: QuantityCollectionMode = Field(QuantityCollectionMode.MANUAL, description="Weight collection mode")
    measurement_mode: MeasurementMode = Field(MeasurementMode.MANUAL, description="Analyzer measurement mode")


class DispatchListResponse(BaseModel):
    """Standard paginated list response for dispatches."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Dispatches fetched successfully", description="Response message")
    items: List[DispatchSchema] = Field(default_factory=list, description="Dispatch records")
    limit: Optional[int] = Field(None, description="Items per page")
    offset: Optional[int] = Field(None, description="Offset")
    total: int = Field(0, description="Total matching records")
    pages: int = Field(1, description="Total pages")
    next_page: Optional[int] = Field(None, description="Next page number")
    has_more: bool = Field(False, description="Has more pages indicator")


class DispatchSingleResponse(BaseModel):
    """Single dispatch response wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Dispatch operation successful", description="Response message")
    data: DispatchSchema = Field(..., description="Dispatch record data")


class DeleteDispatchResponse(BaseModel):
    """Delete response wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Dispatch deleted successfully", description="Response message")
