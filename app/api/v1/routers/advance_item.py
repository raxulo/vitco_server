"""
Advance Item / Advanced Master API Router

Provides REST APIs for managing Advance Items issued to counterparties.

All list endpoints strictly conform to the standard response envelope format:
status, code, message, items, limit, offset, total, pages, next_page, has_more.

Python 3.13+
"""
from app.config.constants import IST
import math
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.v1.schemas.advance_item import (
    AdvanceItemDetailSchema,
    AdvanceItemListResponse,
    AdvanceItemSingleResponse,
    AdvanceSummarySchema,
    CreateAdvanceItemRequest,
)
from app.middleware.authentication import CurrentUser
from app.modules.advanceditem.application.command import (
    AdvanceItemCommand,
    AdvanceListQuery,
    CreateAdvanceCommand,
)
from app.modules.dependencies import GetHandler

router = APIRouter(
    prefix="/advance-items",
    tags=["Advance Items"],
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


def _dto_to_summary_schema(dto) -> AdvanceSummarySchema:
    """Convert AdvanceListDTO or AdvanceDetailDTO to summary schema."""
    adv_date = getattr(dto, "advance_date", None)
    adv_date_str = adv_date.strftime("%Y-%m-%d %H:%M") if adv_date else "-"

    user_role_val = getattr(dto, "user_role", None)
    creator_role_val = getattr(dto, "created_by_role", None)

    items_schema: Optional[List[AdvanceItemDetailSchema]] = None
    if hasattr(dto, "items") and dto.items:
        items_schema = [
            AdvanceItemDetailSchema(
                id=str(it.id),
                item_master_id=str(it.item_master_id),
                item_name=it.item_name,
                item_code=str(it.item_code),
                quantity=float(it.quantity),
                unit_rate=float(it.unit_rate),
                amount=float(it.amount),
            )
            for it in dto.items
        ]

    return AdvanceSummarySchema(
        id=str(dto.id),
        user_id=str(dto.user_id),
        user_name=dto.user_name,
        user_role=user_role_val,
        advance_date=adv_date_str,
        created_by=str(dto.created_by),
        created_by_name=dto.created_by_name,
        created_by_role=creator_role_val,
        notes=dto.notes,
        total_amount=float(dto.total_amount),
        items=items_schema,
    )


# --- 1. List Advance Items ---

@router.get("", response_model=AdvanceItemListResponse)
@router.get("/", response_model=AdvanceItemListResponse)
@router.post("/list", response_model=AdvanceItemListResponse)
async def list_advance_items(
    request: Request,
    limit: int = Query(20, ge=1, le=500, description="Items per page"),
    page: int = Query(1, ge=1, description="Offset for pagination"),
):
    """Fetch paginated list of Advance Item records."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.advance_item_service(request)
    offset = (page - 1) * limit
    try:
        query = AdvanceListQuery(
            owner=user_state,
            page=page,
            size=limit,
        )
        response_dto = await service.list(query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch advance items: {str(exc)}")

    # Get total count from repository count method
    total_count = await service._advance_record_repository.count(owner=user_state)

    items_schema = [_dto_to_summary_schema(item) for item in response_dto.items]
    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return AdvanceItemListResponse(
        status=True,
        code=200,
        message="Advance items list fetched successfully",
        items=items_schema,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
    )


# --- 2. Create Advance Item Record ---
@router.post("", response_model=AdvanceItemSingleResponse)
@router.post("/", response_model=AdvanceItemSingleResponse)
async def create_advance_item(
    request: Request,
    payload: CreateAdvanceItemRequest,
):
    """
    Issue Advance Items to a counterparty user.
    Automatically posts advance payment posting entry to ledger.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.advance_item_service(request)

    item_cmds = tuple(
        AdvanceItemCommand(
            item_master_id=it.item_master_id,
            quantity=Decimal(str(it.quantity)),
        )
        for it in payload.items
    )

    adv_date = payload.advance_date or datetime.now(IST)

    command = CreateAdvanceCommand(
        user_id=payload.user_id,
        advance_date=adv_date,
        created_by=user_state.id,
        items=item_cmds,
        notes=payload.notes,
    )

    try:
        record = await service.create(command)
        detail = await service.get_detail(record.id)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create advance item: {str(exc)}")

    if not detail:
        raise HTTPException(status_code=500, detail="Failed to retrieve created advance item detail")

    return AdvanceItemSingleResponse(
        status=True,
        code=200,
        message="Advance item created and posted successfully",
        data=_dto_to_summary_schema(detail),
    )


# --- 3. Get Advance Item Detail ---

@router.get("/{id}", response_model=AdvanceItemSingleResponse)
async def get_advance_item_detail(
    request: Request,
    id: UUID,
):
    """Get detailed Advance Item record by UUID (including item breakdown)."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    service = GetHandler.advance_item_service(request)

    try:
        detail = await service.get_detail(id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch advance item detail: {str(exc)}")

    if not detail:
        raise HTTPException(status_code=404, detail="Advance item record not found")

    return AdvanceItemSingleResponse(
        status=True,
        code=200,
        message="Advance item detail fetched successfully",
        data=_dto_to_summary_schema(detail),
    )
