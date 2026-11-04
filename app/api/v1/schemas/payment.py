"""
Payment API Schemas

Provides schemas for Payment Overview, History, Outstanding, Pair Statement, and Give/Receive Transfers
conforming to standard paginated response envelope structure (items, limit, offset, total, pages, next_page, has_more).
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class CounterpartyBalanceSchema(BaseModel):
    """Schema for individual counterparty outstanding item."""
    counterparty_id: Optional[str] = Field(None, description="Counterparty User UUID")
    counterparty_name: str = Field(..., description="Name of counterparty")
    counterparty_mobile: Optional[str] = Field(None, description="Mobile number of counterparty")
    balance: float = Field(..., description="Outstanding balance amount (abs value)")
    direction: str = Field("to_collect", description="to_collect or to_pay")
    updated_at: Optional[str] = Field(None, description="Formatted last update date")


class MilkPaymentDetailsSchema(BaseModel):
    """Milk behind a Milk Payment entry (the collection it paid for)."""
    collection_id: str = Field(..., description="Collection UUID the payment was for")
    quantity: Optional[float] = Field(None, description="Milk quantity")
    fat: Optional[float] = Field(None, description="FAT %")
    snf: Optional[float] = Field(None, description="SNF %")
    rate: Optional[float] = Field(None, description="Rate per unit")


class PaymentRecentEntrySchema(BaseModel):
    """Schema for individual payment ledger entry."""
    id: str = Field(..., description="Ledger Entry UUID")
    transfer_id: str = Field(..., description="Transfer UUID")
    counterparty_id: Optional[str] = Field(None, description="Counterparty User UUID")
    counterparty_name: str = Field(..., description="Name of counterparty")
    entry_type: str = Field(..., description="Credit or Debit")
    amount: float = Field(..., description="Transaction amount")
    balance_before: float = Field(..., description="Balance before transaction")
    balance_after: float = Field(..., description="Balance after transaction")
    payment_type_label: str = Field(..., description="Human readable payment label (e.g. Milk Payment, UPI, Bank Transfer)")
    badge_bg: Optional[str] = Field(None, description="Suggested UI badge background color")
    badge_color: Optional[str] = Field(None, description="Suggested UI badge text color")
    icon_class: Optional[str] = Field(None, description="Suggested UI icon class")
    created_at: str = Field(..., description="Formatted timestamp")
    milk_details: Optional[MilkPaymentDetailsSchema] = Field(
        None, description="Quantity / FAT / SNF / rate — only on Milk Payment entries"
    )


class PaymentsOverviewData(BaseModel):
    """Data payload for Payments Overview Dashboard."""
    balance: float = Field(0.0, description="Current Net Account Balance")
    total_to_collect: float = Field(0.0, description="Total amount to collect")
    total_to_pay: float = Field(0.0, description="Total amount to pay")
    to_collect: List[CounterpartyBalanceSchema] = Field(default_factory=list, description="List of counterparties to collect from")
    to_pay: List[CounterpartyBalanceSchema] = Field(default_factory=list, description="List of counterparties to pay to")
    items: List[PaymentRecentEntrySchema] = Field(default_factory=list, description="Recent payment ledger transactions")


class PaymentsOverviewResponse(BaseModel):
    """Response wrapper for Payments Dashboard Overview API."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Payments overview fetched successfully", description="Response message")
    data: PaymentsOverviewData = Field(..., description="Overview dashboard data")


# --- 1. Payment History Response ---

class PaymentHistoryResponse(BaseModel):
    """Standard paginated response wrapper for Payment History API."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Payment ledger history fetched successfully", description="Response message")
    items: List[PaymentRecentEntrySchema] = Field(default_factory=list, description="Ledger entries list")
    limit: Optional[int] = Field(None, description="Maximum number of records per page")
    offset: Optional[int] = Field(None, description="Number of records skipped")
    total: int = Field(0, description="Total number of matching records")
    pages: int = Field(1, description="Total number of pages")
    next_page: Optional[int] = Field(None, description="Next page number if available")
    has_more: bool = Field(False, description="Whether more records are available")
    
    # Metadata fields
    user_id: Optional[str] = Field(None, description="Target User UUID")
    user_name: Optional[str] = Field(None, description="Target User Name")
    start_date: Optional[str] = Field(None, description="Filtered start date")
    end_date: Optional[str] = Field(None, description="Filtered end date")


# --- 2. Payment Outstanding Response ---

class PaymentOutstandingResponse(BaseModel):
    """Standard paginated response wrapper for Outstanding Balances API."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Outstanding balances fetched successfully", description="Response message")
    items: List[CounterpartyBalanceSchema] = Field(default_factory=list, description="Outstanding balance records")
    limit: Optional[int] = Field(None, description="Maximum number of records per page")
    offset: Optional[int] = Field(None, description="Number of records skipped")
    total: int = Field(0, description="Total number of matching records")
    pages: int = Field(1, description="Total number of pages")
    next_page: Optional[int] = Field(None, description="Next page number if available")
    has_more: bool = Field(False, description="Whether more records are available")
    
    # Metadata summary fields
    user_id: Optional[str] = Field(None, description="Target User UUID")
    total_to_collect: float = Field(0.0, description="Total receivable amount")
    total_to_pay: float = Field(0.0, description="Total payable amount")
    net_balance: float = Field(0.0, description="Net balance (to_collect - to_pay)")


# --- 3. Pair Statement / Pair Ledger Schemas ---

class PairUserSummary(BaseModel):
    """Summary schema for user in Pair Statement."""
    id: str = Field(..., description="User UUID")
    name: str = Field(..., description="User Full Name")
    mobile: Optional[str] = Field(None, description="Mobile number")


class PairHistoryItem(BaseModel):
    """Paired transaction record between user and counterparty."""
    transfer_id: str = Field(..., description="Transfer UUID")
    amount: float = Field(..., description="Transaction amount")
    created_at: str = Field(..., description="ISO or formatted timestamp")
    user_entry_type: int = Field(..., description="Entry type for active user (1=Debit, 2=Credit)")
    user_entry_type_label: str = Field(..., description="Credit or Debit")
    user_before: float = Field(..., description="User balance before transaction")
    user_after: float = Field(..., description="User balance after transaction")
    counterparty_before: float = Field(..., description="Counterparty balance before transaction")
    counterparty_after: float = Field(..., description="Counterparty balance after transaction")


class PairStatementResponse(BaseModel):
    """Standard paginated response wrapper for Pair Statement / Pair Ledger API."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Pair statement fetched successfully", description="Response message")
    items: List[PairHistoryItem] = Field(default_factory=list, description="Paired ledger transaction items")
    limit: Optional[int] = Field(None, description="Maximum number of records per page")
    offset: Optional[int] = Field(None, description="Number of records skipped")
    total: int = Field(0, description="Total number of matching paired records")
    pages: int = Field(1, description="Total number of pages")
    next_page: Optional[int] = Field(None, description="Next page number if available")
    has_more: bool = Field(False, description="Whether more records are available")
    
    # Pair Metadata
    from_user: Optional[PairUserSummary] = Field(None, description="Primary user profile")
    counterparty: Optional[PairUserSummary] = Field(None, description="Counterparty user profile")
    start_date: Optional[str] = Field(None, description="Formatted start date")
    end_date: Optional[str] = Field(None, description="Formatted end date")


# --- 4. Post Give/Receive Payment Schemas ---

class PostPaymentRequest(BaseModel):
    """Request schema for creating a payment transaction."""
    counterparty_id: str = Field(..., description="Target Counterparty User UUID")
    action_type: str = Field("give", description="'give' (you pay counterparty) or 'receive' (counterparty pays you)")
    amount: float = Field(..., gt=0.0, description="Transaction amount (must be > 0)")
    payment_method: int = Field(1, description="1=Cash, 2=UPI, 3=Bank Transfer, 4=Online")
    reference: Optional[str] = Field(None, description="Transaction reference code/note")
    description: Optional[str] = Field(None, description="Transaction description")


class PostPaymentData(BaseModel):
    """Response data for completed payment transaction."""
    sender_id: str = Field(..., description="Sender User UUID")
    receiver_id: str = Field(..., description="Receiver User UUID")
    amount: float = Field(..., description="Transferred Amount")
    payment_method: int = Field(..., description="Payment method code")
    idempotency_key: str = Field(..., description="Generated Idempotency Key")


class PostPaymentResponse(BaseModel):
    """Response wrapper for Post Payment API."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Transaction posted successfully", description="Response message")
    data: PostPaymentData = Field(..., description="Post payment result data")
