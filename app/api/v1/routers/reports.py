"""
Reports API Router

Provides REST APIs for generating and viewing analytical reports for MCC and VLCC.
Includes endpoints for VLCC Shift Summary, Member Ledger, Milk Bill Summary,
MCC Shift Summary, MCC VLCC Bill, Dispatch Summary, and custom report queries.

Python 3.13+
"""
from dataclasses import asdict
from datetime import date, datetime
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import ORJSONResponse

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift, MilkType
from app.modules.dependencies import GetHandler
from app.modules.reports.application.dto import ReportResult
from app.modules.reports.application.queries import ReportQuery
from app.modules.reports.domain.enums import ReportType
from app.modules.reports.presentation.request import ReportPreviewRequest
from app.core.clock import today_ist

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


def _serialize_report_result(result: ReportResult) -> dict[str, Any]:
    """Serialize ReportResult dataclass to standardized API response format.

    Web-only columns (`ReportResult.web_only_columns`) are left out of the
    header, rows and ledger rows; the web templates still show them.
    """
    metadata_dict = asdict(result.metadata) if result.metadata else {}
    header = result.header or []
    rows = result.rows or []
    ledger: list[Any] = result.ledger or []

    web_only = result.web_only_columns or {}
    if web_only:
        hidden_keys, hidden_labels = set(web_only), set(web_only.values())

        def visible(row: dict[str, Any]) -> dict[str, Any]:
            # New dicts: the result's rows are shared with the web templates
            return {k: v for k, v in row.items() if k not in hidden_keys}

        header = [h for h in header if h not in hidden_labels]
        rows = [visible(r) for r in rows]
        ledger = [
            {"head": block.head, "rows": [visible(r) for r in block.rows or []], "footer": block.footer}
            for block in ledger
        ]

    return {
        "metadata": metadata_dict,
        "report_type": result.report_type,
        "header": header,
        "footer": result.footer or {},
        "total": result.total,
        "page": result.page,
        "size": result.size,
        "rows": rows,
        "ledger": ledger,
    }


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse string (YYYY-MM-DD or DD/MM/YYYY) to date object."""
    if not date_str or not date_str.strip():
        return None
    val = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    return None


def _parse_shift(shift_val: Optional[Any]) -> Optional[CollectionShift]:
    """Parse shift input into CollectionShift enum."""
    if shift_val is None or shift_val == "":
        return None
    if isinstance(shift_val, CollectionShift):
        return shift_val
    val_str = str(shift_val).strip().lower()
    if val_str in ("0", "morning", "m"):
        return CollectionShift.MORNING
    if val_str in ("1", "evening", "e"):
        return CollectionShift.EVENING
    return None


def _parse_milk_type(milk_val: Optional[Any]) -> Optional[MilkType]:
    """Parse milk type input into MilkType enum."""
    if milk_val is None or milk_val == "":
        return None
    if isinstance(milk_val, MilkType):
        return milk_val
    val_str = str(milk_val).strip().lower()
    if val_str in ("0", "cow"):
        return MilkType.COW
    if val_str in ("1", "buffalo"):
        return MilkType.BUFFALO
    if val_str in ("2", "mixed", "both"):
        return MilkType.MIXED
    return None


# =========================================================
# 1. Report Options & Available Types
# =========================================================
@router.get("/options", response_class=ORJSONResponse)
@router.get("/types", response_class=ORJSONResponse)
async def get_report_types(request: Request):
    """
    Returns available report types dynamically categorized by user role (MCC vs VLCC).
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    vlcc_reports = [
        {"value": ReportType.VLCC_SHIFT_SUMMARY.value, "label": "VLCC Shift Summary"},
        {"value": ReportType.VLCC_MEMBER_LEDGER.value, "label": "Member Ledger"},
        {"value": ReportType.VLCC_MILK_BILL_SUMMARY.value, "label": "VLCC Milk Bill Summary"},
        {"value": ReportType.VLCC_DUPLICATE_RECEIPT.value, "label": "VLCC Duplicate Receipt"},
        {"value": ReportType.DISPATCH_SUMMARY.value, "label": "Dispatch Summary"},
    ]

    mcc_reports = [
        {"value": ReportType.MCC_SHIFT_SUMMARY.value, "label": "MCC Shift Summary"},
        {"value": ReportType.MCC_VLCC_BILL.value, "label": "MCC VLCC Bill"},
        {"value": ReportType.MCC_BILL_COMPARISON.value, "label": "Milk Bill Comparison"},
        {"value": ReportType.MCC_PAYMENT_SUMMARY.value, "label": "MCC Payment Summary"},
        {"value": ReportType.MCC_MILK_BILL_SUMMARY.value, "label": "MCC Milk Bill Summary"},
        {"value": ReportType.MCC_DUPLICATE_RECEIPT.value, "label": "MCC Duplicate Receipt"},
        {"value": ReportType.MCC_WEIGHT_SHIFT_SUMMARY.value, "label": "MCC Weight Shift Summary"},
        {"value": ReportType.MCC_WEIGHT_DATE_WISE.value, "label": "MCC Weight Date Wise"},
        {"value": ReportType.MCC_WEIGHT_VLCC_WISE.value, "label": "MCC Weight VLCC Wise"},
        {"value": ReportType.MCC_WEIGHT_ROUTE_WISE.value, "label": "MCC Weight Route Wise"},
        {"value": ReportType.MCC_WEIGHT_DUPLICATE_RECEIPT.value, "label": "MCC Weight Duplicate Receipt"},
        {"value": ReportType.MCC_FIXED_RATE_SUMMARY.value, "label": "MCC Fixed Rate Summary"},
        {"value": ReportType.MCC_FIXED_RATE_PAYMENT_SUMMARY.value, "label": "MCC Fixed Rate Payment Summary"},
        {"value": ReportType.MCC_LEDGER.value, "label": "Member Ledger"},
    ]

    return ORJSONResponse(
        content={
            "role": user_state.role_type.value,
            "vlcc_reports": vlcc_reports,
            "mcc_reports": mcc_reports,
        }
    )


# =========================================================
# 2. General Report Execution Endpoint (POST / generate)
# =========================================================
@router.post("/generate", response_class=ORJSONResponse)
@router.post("/execute", response_class=ORJSONResponse)
async def generate_report_post(
    payload: ReportPreviewRequest,
    request: Request,
):
    """
    Generate report via POST body request using ReportService handler.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Set default MCC or VLCC owner ID if not explicitly specified
    mcc_id = payload.mcc_id
    vlcc_id = payload.vlcc_id
    if user_state.role_type == Role.MCC and not mcc_id:
        mcc_id = user_state.own_id
    elif user_state.role_type == Role.VLCC and not vlcc_id:
        vlcc_id = user_state.own_id

    query = ReportQuery(
        actor_id=user_state.id,
        report_type=payload.report_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        milk_type=payload.milk_type,
        mcc_id=mcc_id,
        vlcc_id=vlcc_id,
        route_code=payload.route_code,
        member_code=payload.member_code.strip() if payload.member_code else None,
        code_from=payload.code_from,
        code_to=payload.code_to,
        route_from=payload.route_from,
        route_to=payload.route_to,
        start_shift=payload.start_shift,
        end_shift=payload.end_shift,
        page=payload.page,
        size=payload.size,
    )

    report_service = GetHandler.report_service(request)
    try:
        result: ReportResult = await report_service.execute(query)
        serialized = _serialize_report_result(result)
        return ORJSONResponse(content=jsonable_encoder(serialized))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate report: {str(e)}"
        )


# =========================================================
# 3. General Report Execution Endpoint (GET / generate)
# =========================================================
@router.get("/generate", response_class=ORJSONResponse)
@router.get("/execute", response_class=ORJSONResponse)
async def generate_report_get(
    request: Request,
    report_type: str = Query(..., description="Report type identifier (e.g. vlcc_shift_summary)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD or DD/MM/YYYY)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD or DD/MM/YYYY)"),
    start_shift: Optional[str] = Query(None, description="Start shift: 0/morning or 1/evening"),
    end_shift: Optional[str] = Query(None, description="End shift: 0/morning or 1/evening"),
    milk_type: Optional[str] = Query(None, description="Milk type: 0/cow, 1/buffalo, 2/mixed"),
    mcc_id: Optional[str] = Query(None, description="MCC UUID"),
    vlcc_id: Optional[str] = Query(None, description="VLCC UUID"),
    member_code: Optional[str] = Query(None, description="Member code: farmer code (VLCC reports) or VLCC code (MCC reports)"),
    route_code: Optional[str] = Query(None, description="Target route code"),
    code_from: Optional[str] = Query(None, description="Farmer/Code range start"),
    code_to: Optional[str] = Query(None, description="Farmer/Code range end"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(100, ge=1, le=500, description="Items per page"),
):
    """
    Generate report via GET query parameters using ReportService handler.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        rep_type_enum = ReportType(report_type.strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report_type: '{report_type}'. Supported types: {[t.value for t in ReportType]}"
        )

    parsed_mcc_id = UUID(mcc_id.strip()) if mcc_id and mcc_id.strip() else None
    parsed_vlcc_id = UUID(vlcc_id.strip()) if vlcc_id and vlcc_id.strip() else None

    if user_state.role_type == Role.MCC and not parsed_mcc_id:
        parsed_mcc_id = user_state.own_id
    elif user_state.role_type == Role.VLCC and not parsed_vlcc_id:
        parsed_vlcc_id = user_state.own_id

    query = ReportQuery(
        actor_id=user_state.id,
        report_type=rep_type_enum,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        milk_type=_parse_milk_type(milk_type),
        mcc_id=parsed_mcc_id,
        vlcc_id=parsed_vlcc_id,
        route_code=route_code.strip() if route_code else None,
        member_code=member_code.strip() if member_code else None,
        code_from=code_from.strip() if code_from else None,
        code_to=code_to.strip() if code_to else None,
        start_shift=_parse_shift(start_shift),
        end_shift=_parse_shift(end_shift),
        page=page,
        size=size,
    )

    report_service = GetHandler.report_service(request)
    try:
        result: ReportResult = await report_service.execute(query)
        serialized = _serialize_report_result(result)
        return ORJSONResponse(content=jsonable_encoder(serialized))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to generate report: {str(e)}"
        )


# =========================================================
# 4. Shortcut Endpoint: VLCC Shift Summary
# =========================================================
@router.get("/vlcc-shift-summary", response_class=ORJSONResponse)
@router.post("/vlcc-shift-summary", response_class=ORJSONResponse)
async def vlcc_shift_summary(
    request: Request,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    shift: Optional[str] = Query(None, description="0=Morning, 1=Evening"),
    vlcc_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
):
    """Shortcut endpoint for VLCC Shift Summary Report."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    parsed_vlcc_id = UUID(vlcc_id.strip()) if vlcc_id and vlcc_id.strip() else user_state.own_id
    parsed_shift = _parse_shift(shift)

    query = ReportQuery(
        actor_id=user_state.id,
        report_type=ReportType.VLCC_SHIFT_SUMMARY,
        start_date=_parse_date(start_date) or today_ist(),
        end_date=_parse_date(end_date) or today_ist(),
        start_shift=parsed_shift,
        end_shift=parsed_shift,
        vlcc_id=parsed_vlcc_id,
        page=page,
        size=size,
    )

    report_service = GetHandler.report_service(request)
    result = await report_service.execute(query)
    return ORJSONResponse(content=jsonable_encoder(_serialize_report_result(result)))


# =========================================================
# 5. Shortcut Endpoint: Member Ledger
# =========================================================
@router.get("/member-ledger", response_class=ORJSONResponse)
@router.post("/member-ledger", response_class=ORJSONResponse)
async def member_ledger(
    request: Request,
    member_code: Optional[str] = Query(None, description="Farmer code"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vlcc_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
):
    """Shortcut endpoint for Member Ledger Report."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    parsed_vlcc_id = UUID(vlcc_id.strip()) if vlcc_id and vlcc_id.strip() else user_state.own_id

    query = ReportQuery(
        actor_id=user_state.id,
        report_type=ReportType.VLCC_MEMBER_LEDGER,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        member_code=member_code.strip() if member_code else None,
        vlcc_id=parsed_vlcc_id,
        page=page,
        size=size,
    )

    report_service = GetHandler.report_service(request)
    result = await report_service.execute(query)
    return ORJSONResponse(content=jsonable_encoder(_serialize_report_result(result)))


# =========================================================
# 6. Shortcut Endpoint: Dispatch Summary
# =========================================================
@router.get("/dispatch-summary", response_class=ORJSONResponse)
@router.post("/dispatch-summary", response_class=ORJSONResponse)
async def dispatch_summary(
    request: Request,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    vlcc_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
):
    """Shortcut endpoint for Dispatch Summary Report."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    parsed_vlcc_id = UUID(vlcc_id.strip()) if vlcc_id and vlcc_id.strip() else user_state.own_id

    query = ReportQuery(
        actor_id=user_state.id,
        report_type=ReportType.DISPATCH_SUMMARY,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        vlcc_id=parsed_vlcc_id,
        page=page,
        size=size,
    )

    report_service = GetHandler.report_service(request)
    result = await report_service.execute(query)
    return ORJSONResponse(content=jsonable_encoder(_serialize_report_result(result)))


# =========================================================
# 7. Shortcut Endpoint: MCC Shift Summary
# =========================================================
@router.get("/mcc-shift-summary", response_class=ORJSONResponse)
@router.post("/mcc-shift-summary", response_class=ORJSONResponse)
async def mcc_shift_summary(
    request: Request,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    shift: Optional[str] = Query(None),
    mcc_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
):
    """Shortcut endpoint for MCC Shift Summary Report."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if user_state is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    parsed_mcc_id = UUID(mcc_id.strip()) if mcc_id and mcc_id.strip() else user_state.own_id
    parsed_shift = _parse_shift(shift)

    query = ReportQuery(
        actor_id=user_state.id,
        report_type=ReportType.MCC_SHIFT_SUMMARY,
        start_date=_parse_date(start_date),
        end_date=_parse_date(end_date),
        start_shift=parsed_shift,
        end_shift=parsed_shift,
        mcc_id=parsed_mcc_id,
        page=page,
        size=size,
    )

    report_service = GetHandler.report_service(request)
    result = await report_service.execute(query)
    return ORJSONResponse(content=jsonable_encoder(_serialize_report_result(result)))
