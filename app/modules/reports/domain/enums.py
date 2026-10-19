from enum import StrEnum


class ReportType(StrEnum):

    # =========================
    # MCC
    # =========================

    MCC_SHIFT_SUMMARY = "mcc_shift_summary"
    MCC_LEDGER = "mcc_ledger"
    MCC_SUMMARY = "mcc_summary"
    MCC_FIXED_RATE_SUMMARY = "mcc_fixed_rate_summary"
    MCC_FIXED_RATE_PAYMENT_SUMMARY = "mcc_fixed_rate_payment_summary"
    MCC_PAYMENT_SUMMARY = "mcc_payment_summary"
    MCC_VLCC_BILL = "mcc_vlcc_bill"
    MCC_BILL_COMPARISON = "mcc_bill_comparison"
    MCC_VLCC_COMPARISON = "mcc_vlcc_comparison"
    MCC_WEIGHT_SHIFT_SUMMARY = "mcc_weight_shift_summary"
    MCC_WEIGHT_DATE_WISE = "mcc_weight_date_wise"
    MCC_WEIGHT_VLCC_WISE = "mcc_weight_vlcc_wise"
    MCC_WEIGHT_ROUTE_WISE = "mcc_weight_route_wise"
    MCC_MILK_BILL_SUMMARY = "mcc_milk_bill_summary"
    MCC_DUPLICATE_RECEIPT = "mcc_duplicate_receipt"

    # =========================
    # VLCC
    # =========================

    VLCC_SHIFT_SUMMARY = "vlcc_shift_summary"
    VLCC_MEMBER_LEDGER = "vlcc_member_ledger"
    VLCC_DATE_WISE = "vlcc_date_wise"
    VLCC_VLCC_WISE = "vlcc_vlcc_wise"
    VLCC_MILK_BILL_SUMMARY = "vlcc_milk_bill_summary"
    VLCC_ROUTE_WISE = "vlcc_route_wise"
    VLCC_DUPLICATE_RECEIPT = "vlcc_duplicate_receipt"

    # =========================
    # Dispatch
    # =========================

    DISPATCH_SUMMARY = "dispatch_summary"