"""
Collection Pydantic Schemas

Validation schemas for Recent Milk Collection API (Create, Get Recent & Delete).

Python 3.13+
"""
from app.core.clock import IST, to_naive_ist, now_naive_ist
from app.config.settings import Settings
from app.modules.administration.domain.enums import Role
from pydantic import model_validator
from decimal import Decimal
from datetime import datetime
from uuid import UUID
from datetime import UTC
from typing import Any, List, Optional
from pydantic import BaseModel, Field

from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MilkType,
    QuantityCollectionMode,
    MeasurementMode,
    CollectionStatus,
)
from app.modules.masters.advanced.domain.enums import PaymentMode
from app.modules.mcc.domain.enums import MccType

# =============================================================================
# Collection Command
# =============================================================================

class CollectionCommand(BaseModel):
    """Common collection fields used by collection operations."""

    # -------------------------------------------------------------------------
    # Identity / Ownership
    # -------------------------------------------------------------------------

    collection_by: str | UUID | None = Field(
        default=None,
        description="Farmer ID/code for VLCC or VLCC ID/code for MCC",
    )
    
    collection_to: str | UUID | None = Field(
        default=None,
        description="Farmer ID/code for VLCC or VLCC ID/code for MCC",
    )

    collected_at: datetime | None = Field(
        default_factory=now_naive_ist,
        description="Collection timestamp",
    )

    member_code: str | None = None
    member_name: str | None = None
    role: Role | None = None

    # -------------------------------------------------------------------------
    # Collection
    # -------------------------------------------------------------------------

    collected_at: datetime
    shift: CollectionShift

    milk_type: MilkType = MilkType.COW

    quantity: Decimal

    quantity_collection_mode: QuantityCollectionMode = (
        QuantityCollectionMode.MANUAL
    )

    measurement_mode: MeasurementMode = MeasurementMode.MANUAL

    # -------------------------------------------------------------------------
    # Milk Quality
    # -------------------------------------------------------------------------

    fat_percent: Decimal | None = None
    snf_percent: Decimal | None = None
    clr_value: Decimal | None = None

    # -------------------------------------------------------------------------
    # Pricing / Payment
    # -------------------------------------------------------------------------

    rate_per_unit: Decimal = Decimal("0.00")
    total_amount: Decimal = Decimal("0.00")

    payment_mode: PaymentMode = PaymentMode.CASH
    status: CollectionStatus = CollectionStatus.UNPAID

    # -------------------------------------------------------------------------
    # MCC-specific
    # -------------------------------------------------------------------------

    sample_number: int | None = None
    can_count: int | None = None

    detection_value: Decimal | None = None
    mcc_type: MccType | None = None

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------

    rank: int | None = None

    calibration_fat: Decimal | None = None
    calibration_snf: Decimal | None = None

    is_deleted: bool = False

    @model_validator(mode="after")
    def validate_quantity(self):
        if self.quantity is None:
            raise ValueError("quantity is required")

        if self.quantity is not None and self.quantity <= 0:
            raise ValueError("quantity must be greater than zero")

        return self

    def get_quantity(self) -> Decimal:
        return self.quantity or Decimal("0")

    def get_collected_at(self) -> datetime:
        return to_naive_ist(self.collected_at) if self.collected_at else now_naive_ist()


# =============================================================================
# Create
# =============================================================================

class CreateCollectionRequest(CollectionCommand):
    """Request payload for creating a collection."""


# =============================================================================
# Bulk Create
# =============================================================================


class InsertCollectionsRequest(BaseModel):
    """Request schema for inserting multiple collections."""
    collection_by: str | UUID | None = Field(
        default=None,
        description="Farmer ID/code for VLCC or VLCC ID/code for MCC",
    )
    role: Role
    items: list[CollectionCommand] = Field(
        default_factory=list,
        description="Collections to insert.",
    )

    @property
    def total_collection(self) -> int:
        return len(self.items)

# =============================================================================
# Update
# =============================================================================

class UpdateCollectionRequest(BaseModel):
    id: str | UUID

    shift: CollectionShift | None = None
    milk_type: MilkType | None = None

    quantity: Decimal | None = None

    quantity_collection_mode: QuantityCollectionMode | None = None
    measurement_mode: MeasurementMode | None = None

    fat_percent: Decimal | None = None
    snf_percent: Decimal | None = None
    clr_value: Decimal | None = None

    rate_per_unit: Decimal | None = None
    total_amount: Decimal | None = None

    payment_mode: PaymentMode | None = None
    status: CollectionStatus | None = None

    sample_number: int | None = None
    can_count: int | None = None

    detection_value: Decimal | None = None
    mcc_type: MccType | None = None

    rank: int | None = None

    calibration_fat: Decimal | None = None
    calibration_snf: Decimal | None = None

    updated_by: str
    role: Role
    
    
# =============================================================================
# Get Collection List Request (POST)
# =============================================================================

class GetCollectionListRequest(BaseModel):
    """Request payload for filtering and fetching milk collections."""
    limit: int = Field(default=20, ge=1, le=100, description="Max items to fetch (1-100)")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")
    shift: CollectionShift | int | str | None = Field(default=None, description="Filter shift")
    date_from: str | datetime | None = Field(default=None, description="Filter start date")
    date_to: str | datetime | None = Field(default=None, description="Filter end date")
    is_deleted: bool | None = Field(default=None, description="Filter deleted status")
    member_id: str | UUID | None = Field(default=None, description="Filter by VLCC ID or Farmer ID")


# =============================================================================
# Collection Response
# =============================================================================


class CollectionResponseData(CollectionCommand):
    """Collection record returned by the API."""

    id: str | UUID
    is_deleted: bool = Field(default=False, description="True when the collection was soft-deleted.")


# =============================================================================
# Collection List Response
# =============================================================================

class CollectionListResponse(BaseModel):
    """Paginated collection list response."""

    status: bool = Field(
        default=True,
        description="Status indicator.",
    )

    code: int = Field(
        default=200,
        description="Response code.",
    )

    message: str = Field(
        ...,
        description="Response message.",
    )

    items: list[CollectionResponseData] = Field(
        default_factory=list,
        description="Collection records.",
    )

    limit: int | None = Field(
        default=None,
        ge=1,
        description="Maximum number of records.",
    )

    offset: int | None = Field(
        default=None,
        ge=0,
        description="Number of records to skip.",
    )

    total: int = Field(
        default=0,
        ge=0,
        description="Total number of matching records.",
    )

    has_more: bool = Field(
        default=False,
        description="Whether more records are available.",
    )

    next_page: int | None = Field(
        default=None,
        ge=1,
        description="Next page number.",
    )
    pages:int = Field(
        default=None,
        ge=1,
        description="Number of pages.",
    )


class CreateCollectionResponse(BaseModel):
    status:bool = False
    message:str = ""
    collection:CollectionResponseData | None = None

class DeleteCollectionsRequest(BaseModel):
    """Request payload for bulk deleting collection records."""
    ids: list[str | UUID] = Field(default_factory=list, description="List of collection UUIDs to delete")

class DeleteCollectionsResponse(BaseModel):
    status: bool = False
    message: str = ""
    deleted_ids: list = []
    failed_ids: list = []


class BulkCreateCollectionResponse(BaseModel):
    status:bool = False
    message:str = ""
    code: int = 0
    created_count:int = 0
    collections:list[CollectionResponseData] = []