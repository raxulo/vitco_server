"""
Dashboard Pydantic Schemas

Professional, type-safe data validation schemas for User Dashboard.

Python 3.13+
"""
from datetime import date
from typing import Literal
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift

from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ShiftSummary(BaseModel):
    """Collection summary grouped by shift (Morning / Evening)."""
    shift: str = Field(..., description="MORNING or EVENING")
    total_quantity: float = Field(0.0, description="Total liters collected in this shift")
    total_amount: float = Field(0.0, description="Total INR amount for this shift")
    entry_count: int = Field(0, description="Total number of collection entries")
    avg_fat: float = Field(0.0, description="Average FAT percentage")
    avg_snf: float = Field(0.0, description="Average SNF percentage")


class MilkTypeSummary(BaseModel):
    """Collection summary grouped by milk type (COW, BUFFALO, MIXED)."""
    milk_type: str = Field(..., description="COW, BUFFALO, or MIXED")
    total_quantity: float = Field(0.0, description="Total liters collected")
    total_amount: float = Field(0.0, description="Total amount in INR")
    entry_count: int = Field(0, description="Total entries")


class RecentCollectionItem(BaseModel):
    """Recent milk collection receipt item."""
    id: str = Field(..., description="Collection UUID")
    farmer_name: Optional[str] = Field(None, description="Farmer name if applicable")
    farmer_code: Optional[str] = Field(None, description="Farmer code if applicable")
    vlcc_name: Optional[str] = Field(None, description="VLCC name if applicable")
    shift: str = Field(..., description="MORNING / EVENING")
    milk_type: str = Field(..., description="COW / BUFFALO / MIXED")
    quantity: float = Field(..., description="Quantity in liters")
    fat: float = Field(0.0, description="FAT %")
    snf: float = Field(0.0, description="SNF %")
    rate: float = Field(0.0, description="Rate per liter")
    total_amount: float = Field(..., description="Total amount in INR")
    collected_at: str = Field(..., description="ISO timestamp of collection")


class MetricCard(BaseModel):
    """Key metric card displayed on top of dashboard."""
    title: str = Field(..., description="Metric label/title")
    value: Any = Field(..., description="Formatted value")
    subtitle: Optional[str] = Field(None, description="Additional context or unit")
    icon: Optional[str] = Field(None, description="Suggested icon name")


class RoleDashboardData(BaseModel):
    """Role-specific Dashboard payload."""
    cards: List[MetricCard] = Field(default_factory=list, description="Top key metric cards")
    today_quantity: float = Field(0.0, description="Today total milk collected in liters")
    today_amount: float = Field(0.0, description="Today total collection amount in INR")
    monthly_quantity: float = Field(0.0, description="Monthly total milk collected in liters")
    monthly_amount: float = Field(0.0, description="Monthly total collection amount in INR")
    avg_fat: float = Field(0.0, description="Average FAT percentage today")
    avg_snf: float = Field(0.0, description="Average SNF percentage today")
    shifts: List[ShiftSummary] = Field(default_factory=list, description="Shift wise breakdown")
    milk_types: List[MilkTypeSummary] = Field(default_factory=list, description="Milk type wise breakdown")
    recent_collections: List[RecentCollectionItem] = Field(default_factory=list, description="Recent 5-10 collection entries")


class DashboardResponse(BaseModel):
    """Top-level Dashboard API Response schema."""
    status: str = Field("success", description="Status string")
    role: str = Field(..., description="Role string (VLCC, MCC, FARMER, ADMIN)")
    user_name: str = Field(..., description="Logged in user display name")
    user_id: str = Field(..., description="Logged in user UUID")
    server_time: str = Field(..., description="Server current UTC ISO time")
    data: RoleDashboardData = Field(..., description="Dashboard metrics and activity data")


############################################################################################
############################################################################################


class ChartDatasetDto(BaseModel):
    key: str
    label: str
    data: list[int | float]


class ChartInfoDto(BaseModel):
    labels: list[str]
    datasets: list[ChartDatasetDto]


class ChartSummaryDto(BaseModel):
    total: int
    previous_total: int
    change_percent: float | None


class ChartResponseDto(BaseModel):
    period: Literal["1w", "1m", "6m", "1y"]
    group_by: Literal["day", "month"]
    chart_type: Literal["line", "bar", "donut", "area", "pie"]
    start_date: date
    end_date: date
    timezone: str
    summary: ChartSummaryDto
    chart: ChartInfoDto

class CollectionPaymentSummaryData(BaseModel):
    title: str = Field(..., description="Title")
    pending: float = Field(0.0, description="Pending amount in INR")
    paid: float = Field(0.0, description="Paid amount in INR")
    total: float = Field(0.0, description="Total amount in INR")
    
class PaymentSummaryData(BaseModel):
    title: str = Field(..., description="Title")
    balance: float = Field(0.0, description="Amount Balance")
    to_collect: float = Field(0.0, description="Amount to collect from user")
    to_pay: float = Field(0.0, description="Amount to pay to user")

class ParticipateSummaryData(BaseModel):
    title: str = Field(..., description="Title")
    role: Role = Field(..., description="Role type")
    count: int = Field(0, description="Count of users with this role")
    pending: int = Field(0, description="Count of pending users with this role")
    accepted: int = Field(0, description="Count of accepted users with this role")
    supplied_per: int = Field(0, description="Percentage of supplied users with this role")

class ShiftSummaryData(BaseModel):
    shift: CollectionShift = Field(CollectionShift.MORNING, description="MORNING or EVENING")
    total_quantity: float = Field(0.0, description="Total milk collected in liters")
    total_amount: float = Field(0.0, description="Total collection amount in INR")
    avg_fat: float = Field(0.0, description="Average FAT percentage today")
    avg_snf: float = Field(0.0, description="Average SNF percentage today")
    avg_rate: float = Field(0.0, description="Average rate per liter")
    participate: ParticipateSummaryData = Field(..., description="Participate summary")

class DashboardDataResponse(BaseModel):
    """Role-specific Dashboard payload."""
    status: bool = Field(default=True, description="Status")
    message: str = Field(default="Success", description="Message")
    synced_time: str = Field(default="", description="Sync time")
    role: Role = Field(..., description="Role")
    cards: List[MetricCard] = Field(default_factory=list, description="Top key metric cards")
    collection_payment_summary: CollectionPaymentSummaryData | None = Field(default=None, description="Collection Payment summary")
    payment_summary: PaymentSummaryData | None = Field(default=None, description="Payment summary")
    current_shift_summary: ShiftSummaryData | None = Field(default=None, description="Shift summary")
    participate: ParticipateSummaryData | None = Field(default=None, description="Participate summary")
