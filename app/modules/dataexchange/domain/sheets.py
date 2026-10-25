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


COLLECTION_MODES = (("MANUAL", 0), ("AUTOMATIC", 1))
ANALYZER_TYPES = (("TYPE_A", 0), ("TYPE_B", 1), ("TYPE_C", 2), ("TYPE_D", 3))
WEIGHT_UNITS = (("LITER", 0), ("KILOGRAM", 1))
RECEIPT_SIZES = (("SMALL", 0), ("MEDIUM", 1), ("LARGE", 2), ("EXTRA_LARGE", 3))
PRINTER_TYPES = (("NONE", 0), ("THERMAL", 1), ("DOT_MATRIX", 2), ("LASER", 3))
CATTLE_TYPES = (("COW_AND_BUFFALO", 0), ("COW_ONLY", 1), ("BUFFALO_ONLY", 2))

DEFAULT_VLCC_PASSWORD = "Vitco@123"

VLCC_SHEET = SheetSpec(
    name="VLCCs",
    key_column="vlcc_code",
    columns=(
        # VLCC Entity (10 columns)
        ColumnSpec(
            key="vlcc_code", header="VLCC Code", section=Section.ENTITY, kind=ColumnKind.CODE,
            required=True, max_length=30, example="V001",
            help="Unique inside the owner's hierarchy. An existing code updates that VLCC, a new code creates one.",
        ),
        ColumnSpec(
            key="uic_code", header="UIC Code", section=Section.ENTITY, kind=ColumnKind.CODE,
            required=True, max_length=50, example="UIC001",
            help="Unique Identification Code / company registration code.",
        ),
        ColumnSpec(
            key="vlcc_name", header="VLCC Name", section=Section.ENTITY, kind=ColumnKind.TEXT,
            required=True, max_length=150, example="Gokul Dairy Center",
            help="Display name of the village collection center.",
        ),
        ColumnSpec(
            key="contact_person", header="Contact Person", section=Section.ENTITY, kind=ColumnKind.TEXT,
            max_length=150, example="Mahesh Patel",
            help="Primary contact person at the center.",
        ),
        ColumnSpec(
            key="entry_mode", header="Collection Mode", section=Section.ENTITY, kind=ColumnKind.ENUM,
            choices=COLLECTION_MODES, example="MANUAL",
            help="Collection entry mode. Empty on a new VLCC = MANUAL.",
        ),
        ColumnSpec(
            key="route_code", header="Route Code", section=Section.ENTITY, kind=ColumnKind.INT,
            min_value=1, max_value=999999, example="101",
            help="Route master code for milk dispatch.",
        ),
        ColumnSpec(
            key="soc_percentage", header="SOC Percentage", section=Section.ENTITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=100.0, example="0.0",
            help="Society commission / deduction percentage. Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="farmer_enabled", header="Farmer Enabled", section=Section.ENTITY, kind=ColumnKind.BOOL,
            example="YES", help="Whether farmers can be registered and manage themselves. Empty on a new VLCC = YES.",
        ),
        ColumnSpec(
            key="is_active", header="Active", section=Section.ENTITY, kind=ColumnKind.BOOL,
            example="YES", help="Inactive VLCCs cannot operate. Empty on a new VLCC = YES.",
        ),
        ColumnSpec(
            key="assigned_chart_rank", header="Rate Chart Rank", section=Section.ENTITY, kind=ColumnKind.INT,
            min_value=1, max_value=100, example="1",
            help="Which assigned rate chart applies. Empty on a new VLCC = 1.",
        ),

        # User (4 columns)
        ColumnSpec(
            key="user_name", header="User Name", section=Section.USER, kind=ColumnKind.TEXT,
            required=True, max_length=150, example="Gokul Operator",
            help="Login user's full name. Required for a new VLCC.",
        ),
        ColumnSpec(
            key="mobile", header="Mobile", section=Section.USER, kind=ColumnKind.MOBILE,
            required=True, example="9876543210",
            help="10 digits, unique across all users. Required for a new VLCC.",
        ),
        ColumnSpec(
            key="email", header="Email", section=Section.USER, kind=ColumnKind.EMAIL,
            max_length=255, example="gokul@dairy.local",
            help="Unique across all users. Empty on a new VLCC = an auto-generated address.",
        ),
        ColumnSpec(
            key="password", header="Password", section=Section.USER, kind=ColumnKind.PASSWORD,
            import_only=True, min_length=6, max_length=128, example="",
            help=f"Empty on a new VLCC = {DEFAULT_VLCC_PASSWORD}. Never exported.",
        ),

        # Address (4 columns)
        ColumnSpec(
            key="address_line", header="Address Line", section=Section.ADDRESS, kind=ColumnKind.TEXT,
            max_length=255, example="Plot 12, Main Road",
        ),
        ColumnSpec(
            key="city", header="City", section=Section.ADDRESS, kind=ColumnKind.TEXT,
            max_length=100, example="Indore",
        ),
        ColumnSpec(
            key="state", header="State", section=Section.ADDRESS, kind=ColumnKind.TEXT,
            max_length=100, example="Madhya Pradesh",
        ),
        ColumnSpec(
            key="pincode", header="Pincode", section=Section.ADDRESS, kind=ColumnKind.PINCODE,
            example="452001",
        ),

        # Bank (5 columns)
        ColumnSpec(
            key="account_holder", header="Account Holder", section=Section.BANK, kind=ColumnKind.TEXT,
            max_length=150, example="Gokul Dairy Center",
            help="Empty on a new VLCC = User Name.",
        ),
        ColumnSpec(
            key="bank_name", header="Bank Name", section=Section.BANK, kind=ColumnKind.TEXT,
            max_length=150, example="State Bank of India",
        ),
        ColumnSpec(
            key="account_number", header="Account Number", section=Section.BANK, kind=ColumnKind.ACCOUNT_NUMBER,
            example="123456789012",
        ),
        ColumnSpec(
            key="ifsc_code", header="IFSC Code", section=Section.BANK, kind=ColumnKind.IFSC,
            example="SBIN0001234",
        ),
        ColumnSpec(
            key="upi_id", header="UPI ID", section=Section.BANK, kind=ColumnKind.TEXT,
            max_length=100, example="gokul@upi",
        ),

        # Settings (13 columns)
        ColumnSpec(
            key="analyzer_type", header="Analyzer Type", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=ANALYZER_TYPES, example="TYPE_A",
            help="Hardware milk analyzer type. Empty on a new VLCC = TYPE_A.",
        ),
        ColumnSpec(
            key="analyzer_collection_mode", header="Analyzer Mode", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=COLLECTION_MODES, example="MANUAL",
            help="Analyzer reading mode. Empty on a new VLCC = MANUAL.",
        ),
        ColumnSpec(
            key="weight_unit", header="Weight Unit", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=WEIGHT_UNITS, example="LITER",
            help="Measurement unit. Empty on a new VLCC = LITER.",
        ),
        ColumnSpec(
            key="weight_collection_mode", header="Weight Mode", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=COLLECTION_MODES, example="MANUAL",
            help="Weighing scale reading mode. Empty on a new VLCC = MANUAL.",
        ),
        ColumnSpec(
            key="auto_tare_enabled", header="Auto Tare Enabled", section=Section.SETTINGS, kind=ColumnKind.BOOL,
            example="NO", help="Empty on a new VLCC = NO.",
        ),
        ColumnSpec(
            key="morning_collection_start", header="Morning Start", section=Section.SETTINGS, kind=ColumnKind.TIME,
            example="06:00", help="Morning shift start time (HH:MM). Empty on a new VLCC = 06:00.",
        ),
        ColumnSpec(
            key="morning_collection_end", header="Morning End", section=Section.SETTINGS, kind=ColumnKind.TIME,
            example="10:00", help="Morning shift end time (HH:MM). Empty on a new VLCC = 10:00.",
        ),
        ColumnSpec(
            key="evening_collection_start", header="Evening Start", section=Section.SETTINGS, kind=ColumnKind.TIME,
            example="12:00", help="Evening shift start time (HH:MM). Empty on a new VLCC = 12:00.",
        ),
        ColumnSpec(
            key="evening_collection_end", header="Evening End", section=Section.SETTINGS, kind=ColumnKind.TIME,
            example="22:00", help="Evening shift end time (HH:MM). Empty on a new VLCC = 22:00.",
        ),
        ColumnSpec(
            key="receipt_size", header="Receipt Size", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=RECEIPT_SIZES, example="SMALL",
            help="Thermal printer paper size. Empty on a new VLCC = SMALL.",
        ),
        ColumnSpec(
            key="printer_type", header="Printer Type", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=PRINTER_TYPES, example="NONE",
            help="Printer type. Empty on a new VLCC = NONE.",
        ),
        ColumnSpec(
            key="printer_enabled", header="Printer Enabled", section=Section.SETTINGS, kind=ColumnKind.BOOL,
            example="NO", help="Empty on a new VLCC = NO.",
        ),
        ColumnSpec(
            key="cattle_type", header="Cattle Type", section=Section.SETTINGS, kind=ColumnKind.ENUM,
            choices=CATTLE_TYPES, example="COW_AND_BUFFALO",
            help="Supported cattle types. Empty on a new VLCC = COW_AND_BUFFALO.",
        ),

        # Milk Quality Config (8 columns)
        ColumnSpec(
            key="cow_min_fat", header="Cow Min FAT", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="2.5", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="cow_max_fat", header="Cow Max FAT", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="12.0", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="cow_min_snf", header="Cow Min SNF", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="6.0", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="cow_max_snf", header="Cow Max SNF", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="14.0", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="buffalo_min_fat", header="Buffalo Min FAT", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="4.0", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="buffalo_max_fat", header="Buffalo Max FAT", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="15.0", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="buffalo_min_snf", header="Buffalo Min SNF", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="7.0", help="Empty on a new VLCC = 0.0.",
        ),
        ColumnSpec(
            key="buffalo_max_snf", header="Buffalo Max SNF", section=Section.MILK_QUALITY, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="16.0", help="Empty on a new VLCC = 0.0.",
        ),
    ),
)

VLCC_ADDRESS_KEYS = ("address_line", "city", "state", "pincode")
VLCC_BANK_KEYS = ("account_holder", "bank_name", "account_number", "ifsc_code", "upi_id")
VLCC_SETTINGS_KEYS = (
    "analyzer_type", "analyzer_collection_mode", "weight_unit", "weight_collection_mode",
    "auto_tare_enabled", "morning_collection_start", "morning_collection_end",
    "evening_collection_start", "evening_collection_end", "receipt_size",
    "printer_type", "printer_enabled", "cattle_type",
)
VLCC_MILK_QUALITY_KEYS = (
    "cow_min_fat", "cow_max_fat", "cow_min_snf", "cow_max_snf",
    "buffalo_min_fat", "buffalo_max_fat", "buffalo_min_snf", "buffalo_max_snf",
)


PRODATA_SHEET = SheetSpec(
    name="Prodata Rate Chart",
    key_column="row_number",
    columns=(
        ColumnSpec(
            key="row_number", header="Row No", section=Section.RATE, kind=ColumnKind.INT,
            min_value=1, example="1",
            help="Row sequence number. If left blank on import, auto-assigned from row order.",
        ),
        ColumnSpec(
            key="fat_min", header="FAT Min", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.0, max_value=20.0, example="3.0",
            help="Minimum FAT percentage.",
        ),
        ColumnSpec(
            key="fat_max", header="FAT Max", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.0, max_value=20.0, example="4.5",
            help="Maximum FAT percentage.",
        ),
        ColumnSpec(
            key="snf_min", header="SNF Min", section=Section.RATE, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="7.0",
            help="Minimum SNF percentage (optional).",
        ),
        ColumnSpec(
            key="snf_max", header="SNF Max", section=Section.RATE, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="9.0",
            help="Maximum SNF percentage (optional).",
        ),
        ColumnSpec(
            key="fat_rate_per_kg", header="FAT Rate / KG", section=Section.RATE, kind=ColumnKind.FLOAT,
            min_value=0.0, example="350.0",
            help="Rate per kg FAT (in rupees).",
        ),
        ColumnSpec(
            key="snf_rate_per_kg", header="SNF Rate / KG", section=Section.RATE, kind=ColumnKind.FLOAT,
            min_value=0.0, example="250.0",
            help="Rate per kg SNF (in rupees).",
        ),
        ColumnSpec(
            key="snf_cutoff", header="SNF Cut-off", section=Section.RATE, kind=ColumnKind.FLOAT,
            min_value=0.0, max_value=20.0, example="8.0",
            help="SNF threshold below which deduction applies.",
        ),
        ColumnSpec(
            key="snf_deduction", header="SNF Deduction", section=Section.RATE, kind=ColumnKind.FLOAT,
            min_value=0.0, example="2.0",
            help="Deduction rate per unit below cutoff.",
        ),
    ),
)

PRODATA_KEYS = (
    "row_number", "fat_min", "fat_max", "snf_min", "snf_max",
    "fat_rate_per_kg", "snf_rate_per_kg", "snf_cutoff", "snf_deduction",
)


FORMULA_ANIMAL_TYPES = (
    ("COW", 0),
    ("BUFFALO", 1),
)

FORMULA_SHEET = SheetSpec(
    name="Formula Rate Chart",
    key_column="animal_type",
    columns=(
        ColumnSpec(
            key="animal_type", header="Animal / Milk Type", section=Section.RATE, kind=ColumnKind.ENUM,
            required=True, choices=FORMULA_ANIMAL_TYPES, example="COW",
            help="Animal type: COW or BUFFALO.",
        ),
        ColumnSpec(
            key="standard_fat", header="Standard FAT (%)", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.1, max_value=20.0, example="4.0",
            help="Standard reference FAT percentage.",
        ),
        ColumnSpec(
            key="standard_snf", header="Standard SNF (%)", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.1, max_value=20.0, example="8.5",
            help="Standard reference SNF percentage.",
        ),
        ColumnSpec(
            key="standard_rate", header="Standard Rate (₹/L)", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.1, example="35.0",
            help="Standard base market rate in ₹ per liter.",
        ),
        ColumnSpec(
            key="fat_percentage", header="FAT Contribution (%)", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.0, max_value=100.0, example="60.0",
            help="FAT value contribution percentage (FAT% + SNF% must equal 100%).",
        ),
        ColumnSpec(
            key="snf_percentage", header="SNF Contribution (%)", section=Section.RATE, kind=ColumnKind.FLOAT,
            required=True, min_value=0.0, max_value=100.0, example="40.0",
            help="SNF value contribution percentage (FAT% + SNF% must equal 100%).",
        ),
    ),
)

FORMULA_KEYS = (
    "animal_type",
    "standard_fat",
    "standard_snf",
    "standard_rate",
    "fat_percentage",
    "snf_percentage",
)


