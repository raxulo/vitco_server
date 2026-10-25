"""
Data Exchange Sheet Specs

The workbook layout of every exchangeable entity, declared once. The same
spec drives the template, the export, the import validation and the
Instructions sheet (REQ-04).

Python 3.13+
"""

from __future__ import annotations

from app.modules.dataexchange.domain.columns import ColumnKind, ColumnSpec, Section, SheetSpec

MILK_TYPES = (("COW", 0), ("BUFFALO", 1), ("MIXED", 2))

DEFAULT_FARMER_PASSWORD = "Vitco@123"


FARMER_SHEET = SheetSpec(
    name="Farmers",
    key_column="farmer_code",
    columns=(
        # Farmer
        ColumnSpec(
            key="farmer_code", header="Farmer Code", section=Section.ENTITY, kind=ColumnKind.CODE,
            required=True, max_length=30, example="F001",
            help="Unique inside the VLCC. An existing code updates that farmer, a new code creates one.",
        ),
        ColumnSpec(
            key="milk_type", header="Milk Type", section=Section.ENTITY, kind=ColumnKind.ENUM,
            choices=MILK_TYPES, example="COW", help="Empty on a new farmer = MIXED.",
        ),
        ColumnSpec(
            key="assigned_chart_rank", header="Rate Chart Rank", section=Section.ENTITY, kind=ColumnKind.INT,
            min_value=1, max_value=100, example="1", help="Which assigned rate chart applies. Empty on a new farmer = 1.",
        ),
        ColumnSpec(
            key="sms_enabled", header="SMS Enabled", section=Section.ENTITY, kind=ColumnKind.BOOL,
            example="NO", help="Empty on a new farmer = NO.",
        ),
        ColumnSpec(
            key="is_active", header="Active", section=Section.ENTITY, kind=ColumnKind.BOOL,
            example="YES", help="Inactive farmers cannot log in. Empty on a new farmer = YES.",
        ),
        # User
        ColumnSpec(
            key="name", header="Name", section=Section.USER, kind=ColumnKind.TEXT,
            required=True, max_length=150, example="Ram Singh", help="Required for a new farmer.",
        ),
        ColumnSpec(
            key="mobile", header="Mobile", section=Section.USER, kind=ColumnKind.MOBILE,
            required=True, example="9876543210",
            help="10 digits, unique across all users. Required for a new farmer.",
        ),
        ColumnSpec(
            key="email", header="Email", section=Section.USER, kind=ColumnKind.EMAIL,
            max_length=255, example="ram@example.com",
            help="Unique across all users. Empty on a new farmer = a generated address.",
        ),
        ColumnSpec(
            key="password", header="Password", section=Section.USER, kind=ColumnKind.PASSWORD,
            import_only=True, min_length=6, max_length=128, example="",
            help=f"Empty on a new farmer = {DEFAULT_FARMER_PASSWORD}. Never exported.",
        ),
        # Address
        ColumnSpec(key="address_line", header="Address Line", section=Section.ADDRESS, kind=ColumnKind.TEXT,
                   max_length=255, example="Main Road"),
        ColumnSpec(key="city", header="City", section=Section.ADDRESS, kind=ColumnKind.TEXT,
                   max_length=100, example="Indore"),
        ColumnSpec(key="state", header="State", section=Section.ADDRESS, kind=ColumnKind.TEXT,
                   max_length=100, example="Madhya Pradesh"),
        ColumnSpec(key="pincode", header="Pincode", section=Section.ADDRESS, kind=ColumnKind.PINCODE,
                   example="452001"),
        # Bank
        ColumnSpec(key="account_holder", header="Account Holder", section=Section.BANK, kind=ColumnKind.TEXT,
                   max_length=150, example="Ram Singh", help="Empty = the farmer's name."),
        ColumnSpec(key="bank_name", header="Bank Name", section=Section.BANK, kind=ColumnKind.TEXT,
                   max_length=150, example="State Bank of India"),
        ColumnSpec(key="account_number", header="Account Number", section=Section.BANK,
                   kind=ColumnKind.ACCOUNT_NUMBER, example="123456789012"),
        ColumnSpec(key="ifsc_code", header="IFSC Code", section=Section.BANK, kind=ColumnKind.IFSC,
                   example="SBIN0001234"),
        ColumnSpec(key="upi_id", header="UPI ID", section=Section.BANK, kind=ColumnKind.TEXT,
                   max_length=100, example="ram@upi"),
    ),
)

FARMER_ADDRESS_KEYS = ("address_line", "city", "state", "pincode")
FARMER_BANK_KEYS = ("account_holder", "bank_name", "account_number", "ifsc_code", "upi_id")
