"""
Payment API Router

Provides Payments Dashboard Overview, Ledger History, Outstanding Balances,
Pair Statement / Pair Ledger, and Give/Receive Payment Transfer APIs.

All list endpoints strictly conform to the standard response envelope format:
status, code, message, items, limit, offset, total, pages, next_page, has_more.

Python 3.13+
"""
import math
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.api.v1.schemas.payment import (
    CounterpartyBalanceSchema,
    MilkPaymentDetailsSchema,
    PairHistoryItem,
    PairStatementResponse,
    PairUserSummary,
    PaymentHistoryResponse,
    PaymentOutstandingResponse,
    PaymentRecentEntrySchema,
    PaymentsOverviewData,
    PaymentsOverviewResponse,
    PostPaymentData,
    PostPaymentRequest,
    PostPaymentResponse,
)
from app.core.numeric import truncate_float
from app.middleware.authentication import CurrentUser
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dependencies import GetHandler
from app.modules.payments.application.command import PostPaymentCommand
from app.modules.payments.domain.enums import PaymentMethod, PaymentSourceType
from app.modules.payments.infrastructure.repository import PaymentLedgerRepository

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
)


def _compute_pagination(total: int, limit: int, offset: int):
    """Compute pagination metadata (pages, next_page, has_more)."""
    limit_val = max(1, limit)
    offset_val = max(0, offset)
    pages = math.ceil(total / limit_val) if total > 0 else 1
    current_page = (offset_val // limit_val) + 1
    has_more = (offset_val + limit_val) < total
    next_page = (current_page + 1) if has_more else None
    return {
        "limit": limit_val,
        "offset": offset_val,
        "total": total,
        "pages": pages,
        "next_page": next_page,
        "has_more": has_more,
    }


def _milk_details_schema(entry, milk_details: dict | None) -> MilkPaymentDetailsSchema | None:
    """Milk Payment entries carry the quantity / FAT / SNF / rate of their collection."""
    source_id = getattr(entry, "source_id", None)
    detail = (milk_details or {}).get(source_id) if source_id is not None else None
    if detail is None:
        return None

    def number(value):
        return truncate_float(value, 2) if value is not None else None

    return MilkPaymentDetailsSchema(
        collection_id=str(detail.collection_id),
        quantity=number(detail.quantity),
        fat=number(detail.fat),
        snf=number(detail.snf),
        rate=number(detail.rate),
    )


def _format_entry_to_schema(entry, milk_details: dict | None = None) -> PaymentRecentEntrySchema:
    """Helper to convert domain/infra ledger entry to Pydantic schema."""
    s_type = int(getattr(entry, "source_type", 0) or 0)
    p_method = int(getattr(entry, "payment_method", 0) or 0)

    if s_type == 2:
        payment_type_label = "Milk Payment"
        badge_bg = "#dbeafe"
        badge_color = "#1e40af"
        icon_class = "fa-cow"
    elif p_method == 2:
        payment_type_label = "UPI"
        badge_bg = "#dcfce7"
        badge_color = "#15803d"
        icon_class = "fa-mobile-screen-button"
    elif p_method == 3:
        payment_type_label = "Bank Transfer"
        badge_bg = "#e0f2fe"
        badge_color = "#0369a1"
        icon_class = "fa-building-columns"
    elif p_method == 4:
        payment_type_label = "Online"
        badge_bg = "#f3e8ff"
        badge_color = "#7e22ce"
        icon_class = "fa-globe"
    elif p_method == 1:
        payment_type_label = "Offline (Cash)"
        badge_bg = "#fef9c3"
        badge_color = "#854d0e"
        icon_class = "fa-money-bill-wave"
    elif s_type == 4:
        payment_type_label = "Advance"
        badge_bg = "#ffedd5"
        badge_color = "#c2410c"
        icon_class = "fa-hand-holding-dollar"
    elif s_type == 3:
        payment_type_label = "Adjustment"
        badge_bg = "#f3f4f6"
        badge_color = "#374151"
        icon_class = "fa-sliders"
    else:
        payment_type_label = "Manual"
        badge_bg = "#f1f5f9"
        badge_color = "#475569"
        icon_class = "fa-receipt"

    entry_id = str(getattr(entry, "id", ""))
    transfer_id = str(getattr(entry, "transfer_id", ""))
    counterparty_id = str(getattr(entry, "counterparty_id", "")) if getattr(entry, "counterparty_id", None) else None
    counterparty_name = getattr(entry, "counterparty_name", None) or "System"
    entry_type_num = getattr(entry, "entry_type", 1)
    entry_type_str = "Credit" if entry_type_num == 2 else "Debit"
    created_dt = getattr(entry, "created_at", None)
    created_dt_str = created_dt.strftime("%Y-%m-%d %H:%M") if created_dt else "-"

    return PaymentRecentEntrySchema(
        id=entry_id,
        transfer_id=transfer_id,
        counterparty_id=counterparty_id,
        counterparty_name=counterparty_name,
        entry_type=entry_type_str,
        amount=float(getattr(entry, "amount", 0.0)),
        balance_before=float(getattr(entry, "balance_before", 0.0)),
        balance_after=float(getattr(entry, "balance_after", 0.0)),
        payment_type_label=payment_type_label,
        badge_bg=badge_bg,
        badge_color=badge_color,
        icon_class=icon_class,
        created_at=created_dt_str,
        milk_details=_milk_details_schema(entry, milk_details),
    )


# --- 1. Overview API ---

@router.get("/overview", response_model=PaymentsOverviewData)
@router.get("/overview/", response_model=PaymentsOverviewData)
@router.get("/dashboard", response_model=PaymentsOverviewData)
async def get_payments_overview(
    request: Request,
    recent_limit: int = Query(default=10, ge=1, le=100, description="Max recent transactions to fetch"),
):
    """Get Payments Dashboard Overview for Logged-In User."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.payment_posting_service(request)

    try:
        balance_dec = await service.get_user_balance(user_state.id)
        raw_outstanding = await service.get_user_outstanding(user_state.id)
        raw_recent = await service.transaction_history_by_user(user_state.id, limit=recent_limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch payment overview: {str(exc)}")

    balance = float(balance_dec or 0.0)
    to_collect: List[CounterpartyBalanceSchema] = []
    to_pay: List[CounterpartyBalanceSchema] = []
    total_to_collect = 0.0
    total_to_pay = 0.0

    for item in raw_outstanding:
        val = float(getattr(item, "balance", 0.0) or 0.0)
        c_id = str(getattr(item, "counterparty_id", "")) if getattr(item, "counterparty_id", None) else None
        c_name = getattr(item, "counterparty_name", None) or "System"
        c_mobile = getattr(item, "counterparty_mobile", None)
        updated_dt = getattr(item, "updated_at", None)
        formatted_dt = updated_dt.strftime("%Y-%m-%d") if updated_dt else "-"

        if val > 0:
            to_collect.append(
                CounterpartyBalanceSchema(
                    counterparty_id=c_id,
                    counterparty_name=c_name,
                    counterparty_mobile=c_mobile,
                    balance=round(val, 2),
                    direction="to_collect",
                    updated_at=formatted_dt,
                )
            )
            total_to_collect += val
        elif val < 0:
            abs_val = abs(val)
            to_pay.append(
                CounterpartyBalanceSchema(
                    counterparty_id=c_id,
                    counterparty_name=c_name,
                    counterparty_mobile=c_mobile,
                    balance=round(abs_val, 2),
                    direction="to_pay",
                    updated_at=formatted_dt,
                )
            )
            total_to_pay += abs_val

    recent_milk = await service.milk_details_for(raw_recent)
    recent_entries: List[PaymentRecentEntrySchema] = [_format_entry_to_schema(entry, recent_milk) for entry in raw_recent]

    overview_data = PaymentsOverviewData(
        balance=round(balance, 2),
        total_to_collect=round(total_to_collect, 2),
        total_to_pay=round(total_to_pay, 2),
        to_collect=to_collect,
        to_pay=to_pay,
        items=recent_entries,
    )

    return overview_data


# --- 2. Payment History API ---

@router.get("/history", response_model=PaymentHistoryResponse)
@router.get("/history/", response_model=PaymentHistoryResponse)
@router.post("/history", response_model=PaymentHistoryResponse)
async def get_payment_history(
    request: Request,
    counterparty_id: Optional[str] = Query(None, description="Optional target user UUID (defaults to logged-in user)"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=500, description="Max entries to return per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Fetch Payment Ledger History.
    Conforms strictly to standard response envelope: items, limit, offset, total, pages, next_page, has_more.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.payment_posting_service(request)
    target_user_id = None
    target_user_name = getattr(user_state, "name", "Logged-In User")

    if counterparty_id and counterparty_id.strip():
        try:
            target_user_id = UUID(counterparty_id.strip())
        except Exception:
            target_user_id = None

    start_dt = None
    end_dt = None
    if start_date and start_date.strip():
        try:
            start_dt = datetime.strptime(start_date.strip(), "%Y-%m-%d")
        except ValueError:
            pass

    if end_date and end_date.strip():
        try:
            end_dt = datetime.strptime(end_date.strip() + " 23:59:59", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    try:
        # Fetch entries up to offset + limit + 500 for total calculation
        raw_entries = await service.transaction_history_by_user(
            user_id=user_state.id,
            counterparty_id=target_user_id,
            start_date=start_dt,
            end_date=end_dt,
            limit=offset + limit + 1000,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch payment history: {str(exc)}")

    total_count = len(raw_entries)
    page_entries = raw_entries[offset : offset + limit]
    # Milk details only for the page actually returned
    milk_details = await service.milk_details_for(page_entries)
    paginated_items = [_format_entry_to_schema(e, milk_details) for e in page_entries]

    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return PaymentHistoryResponse(
        status=True,
        code=200,
        message="Payment ledger history fetched successfully",
        items=paginated_items,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
        user_id=str(target_user_id),
        user_name=target_user_name,
        start_date=start_date,
        end_date=end_date,
    )


# --- 3. Outstanding Balances API ---

@router.get("/outstanding", response_model=PaymentOutstandingResponse)
@router.get("/outstanding/", response_model=PaymentOutstandingResponse)
@router.post("/outstanding", response_model=PaymentOutstandingResponse)
async def get_outstanding_balances(
    request: Request,
    user_id: Optional[str] = Query(None, description="Optional target user UUID (defaults to logged-in user)"),
    limit: int = Query(20, ge=1, le=500, description="Max entries per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Fetch Outstanding Counterparty Balances.
    Conforms strictly to standard response envelope: items, limit, offset, total, pages, next_page, has_more.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.payment_posting_service(request)

    target_user_id = user_state.id
    if user_id and user_id.strip():
        try:
            target_user_id = UUID(user_id.strip())
        except ValueError:
            pass

    try:
        raw_records = await service.get_user_outstanding(user_id=target_user_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch outstanding balances: {str(exc)}")

    total_to_collect = 0.0
    total_to_pay = 0.0
    all_records: List[CounterpartyBalanceSchema] = []

    for item in raw_records:
        val = float(getattr(item, "balance", 0.0) or 0.0)
        c_id = str(getattr(item, "counterparty_id", "")) if getattr(item, "counterparty_id", None) else None
        c_name = getattr(item, "counterparty_name", None) or "System"
        c_mobile = getattr(item, "counterparty_mobile", None)
        updated_dt = getattr(item, "updated_at", None)
        formatted_dt = updated_dt.strftime("%Y-%m-%d") if updated_dt else "-"

        direction = "to_collect" if val > 0 else "to_pay"
        abs_val = abs(val)

        if val > 0:
            total_to_collect += val
        elif val < 0:
            total_to_pay += abs_val

        all_records.append(
            CounterpartyBalanceSchema(
                counterparty_id=c_id,
                counterparty_name=c_name,
                counterparty_mobile=c_mobile,
                balance=round(abs_val, 2),
                direction=direction,
                updated_at=formatted_dt,
            )
        )

    net_balance = round(total_to_collect - total_to_pay, 2)
    total_count = len(all_records)
    paginated_items = all_records[offset : offset + limit]

    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return PaymentOutstandingResponse(
        status=True,
        code=200,
        message="Outstanding balances fetched successfully",
        items=paginated_items,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
        user_id=str(target_user_id),
        total_to_collect=round(total_to_collect, 2),
        total_to_pay=round(total_to_pay, 2),
        net_balance=net_balance,
    )


# --- 4. Pair Statement / Pair Ledger API ---

@router.get("/pair-statement", response_model=PairStatementResponse)
@router.get("/pair-statement/", response_model=PairStatementResponse)
@router.get("/pair-ledger", response_model=PairStatementResponse)
@router.post("/pair-statement", response_model=PairStatementResponse)
@router.post("/pair-ledger", response_model=PairStatementResponse)
async def get_pair_statement(
    request: Request,
    counterparty_id: str = Query(..., description="Counterparty user UUID (required)"),
    from_user_id: Optional[str] = Query(None, description="Primary user UUID (defaults to logged-in user)"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=500, description="Max transaction pairs to fetch per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """
    Fetch Pair Ledger Statement between two parties.
    Conforms strictly to standard response envelope: items, limit, offset, total, pages, next_page, has_more.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    db_manager = request.app.state.application.container.database

    try:
        cp_uuid = UUID(counterparty_id.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid counterparty_id UUID format")

    # Resolve from_user
    from_user_id_val = user_state.id
    from_user_name = getattr(user_state, "name", "User")
    from_user_mobile = getattr(user_state, "mobile", None)

    if from_user_id and from_user_id.strip():
        try:
            f_uuid = UUID(from_user_id.strip())
            stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == f_uuid)
            res = await db_manager.session.execute(stmt)
            fetched_f = res.one_or_none()
            if fetched_f:
                from_user_id_val = fetched_f.id
                from_user_name = fetched_f.name
                from_user_mobile = fetched_f.mobile
        except Exception:
            pass

    # Resolve counterparty
    stmt = select(UserModel.id, UserModel.name, UserModel.mobile).where(UserModel.id == cp_uuid)
    res = await db_manager.session.execute(stmt)
    cp_user = res.one_or_none()
    if not cp_user:
        raise HTTPException(status_code=404, detail="Counterparty user not found")

    start_dt, end_dt = None, None
    start_date_str, end_date_str = None, None

    if start_date and start_date.strip():
        start_date_str = start_date.strip()
        try:
            start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        except ValueError:
            start_dt = None

    if end_date and end_date.strip():
        end_date_str = end_date.strip()
        try:
            end_dt = datetime.strptime(end_date_str + " 23:59:59", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            end_dt = None

    ledger_repo = PaymentLedgerRepository(db_manager.session)

    try:
        user_entries = await ledger_repo.get_pair_history(
            user_id=from_user_id_val,
            counterparty_id=cp_uuid,
            start_date=start_dt,
            end_date=end_dt,
            limit=offset + limit + 1000,
        )
        counterparty_entries = await ledger_repo.get_pair_history(
            user_id=cp_uuid,
            counterparty_id=from_user_id_val,
            start_date=start_dt,
            end_date=end_dt,
            limit=offset + limit + 1000,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch pair history: {str(exc)}")

    cp_map = {e.transfer_id: e for e in counterparty_entries}
    all_pair_history: List[PairHistoryItem] = []

    for ue in user_entries:
        ce = cp_map.get(ue.transfer_id)
        created_dt = getattr(ue, "created_at", None)
        created_dt_str = created_dt.strftime("%Y-%m-%d %H:%M") if created_dt else "-"
        entry_type_num = int(getattr(ue, "entry_type", 1))

        all_pair_history.append(
            PairHistoryItem(
                transfer_id=str(ue.transfer_id),
                amount=float(getattr(ue, "amount", 0.0)),
                created_at=created_dt_str,
                user_entry_type=entry_type_num,
                user_entry_type_label="Credit" if entry_type_num == 2 else "Debit",
                user_before=float(getattr(ue, "balance_before", 0.0)),
                user_after=float(getattr(ue, "balance_after", 0.0)),
                counterparty_before=float(getattr(ce, "balance_before", 0.0)) if ce else 0.0,
                counterparty_after=float(getattr(ce, "balance_after", 0.0)) if ce else 0.0,
            )
        )

    total_count = len(all_pair_history)
    paginated_items = all_pair_history[offset : offset + limit]

    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return PairStatementResponse(
        status=True,
        code=200,
        message="Pair statement fetched successfully",
        items=paginated_items,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
        from_user=PairUserSummary(
            id=str(from_user_id_val),
            name=from_user_name,
            mobile=from_user_mobile,
        ),
        counterparty=PairUserSummary(
            id=str(cp_user.id),
            name=cp_user.name,
            mobile=cp_user.mobile,
        ),
        start_date=start_date_str,
        end_date=end_date_str,
    )


# --- 5. Give / Receive Payment Transfer API ---

@router.post("/transfer", response_model=PostPaymentResponse)
@router.post("/give-receive", response_model=PostPaymentResponse)
async def post_payment_transfer(
    request: Request,
    payload: PostPaymentRequest,
):
    """Post Give/Receive Payment transaction between logged-in user and counterparty."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.payment_posting_service(request)
    db_manager = request.app.state.application.container.database

    try:
        cp_uuid = UUID(payload.counterparty_id.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid counterparty_id UUID format")

    stmt = select(UserModel.id).where(UserModel.id == cp_uuid)
    res = await db_manager.session.execute(stmt)
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Target counterparty user not found")

    action = payload.action_type.lower().strip()
    if action == "give":
        sender_id = cp_uuid
        receiver_id = user_state.id
    elif action == "receive":
        sender_id = user_state.id
        receiver_id = cp_uuid
    else:
        raise HTTPException(status_code=400, detail="action_type must be either 'give' or 'receive'")

    try:
        method_enum = PaymentMethod(payload.payment_method)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payment_method. Allowed: 1 (Cash), 2 (UPI), 3 (Bank), 4 (Online)")

    idempotency_key = str(uuid.uuid4())

    cmd = PostPaymentCommand(
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=Decimal(str(payload.amount)),
        source_type=PaymentSourceType.MANUAL,
        payment_method=method_enum,
        idempotency_key=idempotency_key,
        reference=payload.reference if payload.reference else None,
        description=payload.description if payload.description else None,
    )

    try:
        await service.post(cmd)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to post payment transaction: {str(exc)}")

    return PostPaymentResponse(
        status=True,
        code=200,
        message="Payment transaction posted successfully",
        data=PostPaymentData(
            sender_id=str(sender_id),
            receiver_id=str(receiver_id),
            amount=payload.amount,
            payment_method=payload.payment_method,
            idempotency_key=idempotency_key,
        ),
    )
