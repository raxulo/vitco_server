"""
Dispatch API Router

Provides REST APIs for managing milk dispatches from VLCC centers.
Compatible with mobile collection clients and web portal.

All list endpoints strictly conform to the standard response envelope format:
status, code, message, items, limit, offset, total, pages, next_page, has_more.

Python 3.13+
"""
from decimal import Decimal
from datetime import datetime, time, timezone
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.api.v1.schemas.dispatch import (
    CreateDispatchRequest,
    DeleteDispatchResponse,
    DispatchListResponse,
    DispatchSchema,
    DispatchSingleResponse,
    UpdateDispatchRequest,
)
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MeasurementMode,
    QuantityCollectionMode,
)
from app.modules.collections.vlcc_collection.application.dispatch_command import (
    CreateDispatchCommand,
    DeleteDispatchCommand,
    GetDispatchQuery,
    ListDispatchesQuery,
    UpdateDispatchCommand,
)
from app.modules.collections.vlcc_collection.domain.dispatch_exceptions import (
    DispatchNotFoundException,
)
from app.modules.dependencies import GetHandler
from app.modules.vlcc.infrastructure.models import VlccModel

router = APIRouter(
    prefix="/dispatches",
    tags=["Dispatches"],
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


def _dto_to_schema(dto, vlcc_name: Optional[str] = None) -> DispatchSchema:
    """Helper to convert DispatchDto / DispatchListDto to Pydantic DispatchSchema."""
    dt = dto.collected_at
    qty_mode = dto.quantity_collection_mode
    meas_mode = dto.measurement_mode
    shift = getattr(dto, "shift", CollectionShift.MORNING)

    name = getattr(dto, "vlcc_name", None) or vlcc_name

    return DispatchSchema(
        id=str(dto.id),
        vlcc_id=str(dto.vlcc_id),
        vlcc_name=name,
        collected_at=dt.isoformat(),
        shift=shift,
        fat_percent=float(dto.fat_percent),
        snf_percent=float(dto.snf_percent),
        quantity=float(dto.quantity),
        can_count=dto.can_count,
        quantity_collection_mode=qty_mode,
        measurement_mode=meas_mode,
    )


async def _resolve_vlcc_id(
    request: Request,
    user_state: CurrentUser,
) -> UUID:
    """Resolve target VLCC UUID from logged-in user state."""
    if user_state.role_type == Role.VLCC:
        if user_state.own_id:
            return user_state.own_id

        # Fallback lookup in database
        handler = GetHandler.dispatch_handler(request)
        stmt = select(VlccModel.id).where(VlccModel.user_id == user_state.id).limit(1)
        vlcc_id = await handler._repository._session.scalar(stmt)
        if vlcc_id:
            return vlcc_id

    raise HTTPException(
        status_code=400,
        detail="Only logged-in VLCC users can record milk dispatches, or user is not associated with a VLCC.",
    )


# --- 1. List Dispatches ---

@router.get("", response_model=DispatchListResponse)
@router.get("/", response_model=DispatchListResponse)
@router.post("/list", response_model=DispatchListResponse)
async def list_dispatches(
    request: Request,
    vlcc_id: Optional[UUID] = Query(None, description="Filter by VLCC UUID"),
    shift: Optional[CollectionShift] = Query(None, description="Filter by shift (0: MORNING, 1: EVENING)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Fetch paginated dispatches with date and VLCC filtering."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.dispatch_handler(request)

    # Scoping: if user is VLCC, force their own vlcc_id
    effective_vlcc_id = vlcc_id
    if user_state.role_type == Role.VLCC:
        if user_state.own_id:
            effective_vlcc_id = user_state.own_id
        else:
            stmt = select(VlccModel.id).where(VlccModel.user_id == user_state.id).limit(1)
            effective_vlcc_id = await handler._repository._session.scalar(stmt)

    s_date: Optional[datetime] = None
    e_date: Optional[datetime] = None

    if start_date and start_date.strip():
        try:
            s_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except Exception:
            pass

    if end_date and end_date.strip():
        try:
            d = datetime.strptime(end_date.strip(), "%Y-%m-%d")
            e_date = datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        except Exception:
            pass

    page = (offset // max(1, limit)) + 1

    try:
        total_count = await handler.count(
            vlcc_id=effective_vlcc_id,
            shift=shift,
            start_date=s_date,
            end_date=e_date,
        )

        dtos = await handler.list(
            ListDispatchesQuery(
                vlcc_id=effective_vlcc_id,
                shift=shift,
                start_date=s_date,
                end_date=e_date,
                page=page,
                size=limit,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dispatches: {str(exc)}")

    items_schema = [_dto_to_schema(d) for d in dtos]
    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return DispatchListResponse(
        status=True,
        code=200,
        message="Dispatches fetched successfully",
        items=items_schema,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
    )


# --- 2. Create Dispatch ---

@router.post("", response_model=DispatchSingleResponse)
@router.post("/", response_model=DispatchSingleResponse)
async def create_dispatch(
    request: Request,
    payload: CreateDispatchRequest,
):
    """Create a new milk dispatch note."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.dispatch_handler(request)
    resolved_vlcc_id = await _resolve_vlcc_id(request, user_state)
    command = CreateDispatchCommand(
        vlcc_id=resolved_vlcc_id,
        collected_at=payload.get_collected_at(),
        shift=payload.shift,
        fat_percent=Decimal(str(payload.fat_percent)),
        snf_percent=Decimal(str(payload.snf_percent)),
        quantity=Decimal(str(payload.quantity)),
        can_count=payload.can_count,
        quantity_collection_mode=payload.quantity_collection_mode,
        measurement_mode=payload.measurement_mode,
    )

    try:
        created_dto = await handler.create(command)
        vlcc_name = await handler.get_vlcc_name(resolved_vlcc_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create dispatch: {str(exc)}")

    return DispatchSingleResponse(
        status=True,
        code=200,
        message="Milk dispatch recorded successfully",
        data=_dto_to_schema(created_dto, vlcc_name=vlcc_name),
    )


# --- 3. Get Single Dispatch ---

@router.get("/{id}", response_model=DispatchSingleResponse)
async def get_dispatch(
    request: Request,
    id: UUID,
):
    """Get single dispatch by UUID."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.dispatch_handler(request)

    try:
        dto = await handler.get_with_vlcc(id)
    except DispatchNotFoundException:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch dispatch: {str(exc)}")

    return DispatchSingleResponse(
        status=True,
        code=200,
        message="Dispatch fetched successfully",
        data=_dto_to_schema(dto),
    )


# --- 4. Update Dispatch ---

@router.put("/{id}", response_model=DispatchSingleResponse)
async def update_dispatch(
    request: Request,
    id: Optional[UUID|str],
    payload: UpdateDispatchRequest,
):
    """Update an existing dispatch note."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.dispatch_handler(request)
    id_uuid: UUID | None = None

    if isinstance(id, str) and id is not None and id.strip() != "":
        id_uuid = UUID(id.strip())
    elif isinstance(id, UUID):
        id_uuid = id
    elif id is None or id == "" or id.strip() == "":
        id_uuid = user_state.own_id

    if id_uuid is None or user_state.role_type != Role.VLCC:
        raise HTTPException(status_code=400, detail="Unauthorized or dispatch ID is required")

    try:
        existing = await handler.get(GetDispatchQuery(id=id_uuid))
    except DispatchNotFoundException:
        raise HTTPException(status_code=404, detail="Dispatch not found")

    from decimal import Decimal
    fat = Decimal(str(payload.fat_percent)) if payload.fat_percent is not None else existing.fat_percent
    snf = Decimal(str(payload.snf_percent)) if payload.snf_percent is not None else existing.snf_percent
    qty = Decimal(str(payload.quantity)) if payload.quantity is not None else existing.quantity
    cans = payload.can_count if payload.can_count is not None else existing.can_count
    collected_at = payload.get_collected_at() or existing.collected_at
    shift = payload.shift if payload.shift is not None else getattr(existing, "shift", CollectionShift.MORNING)
    qty_mode = payload.quantity_collection_mode if payload.quantity_collection_mode is not None else existing.quantity_collection_mode
    meas_mode = payload.measurement_mode if payload.measurement_mode is not None else existing.measurement_mode

    command = UpdateDispatchCommand(
        id=id_uuid,
        vlcc_id=existing.vlcc_id,
        collected_at=collected_at,
        shift=shift,
        fat_percent=fat,
        snf_percent=snf,
        quantity=qty,
        can_count=cans,
        quantity_collection_mode=qty_mode,
        measurement_mode=meas_mode,
    )

    try:
        updated_dto = await handler.update(command)
        vlcc_name = await handler.get_vlcc_name(existing.vlcc_id)
    except DispatchNotFoundException:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to update dispatch: {str(exc)}")

    return DispatchSingleResponse(
        status=True,
        code=200,
        message="Dispatch updated successfully",
        data=_dto_to_schema(updated_dto, vlcc_name=vlcc_name),
    )


# --- 5. Delete Dispatch ---

@router.delete("/{id}", response_model=DeleteDispatchResponse)
async def delete_dispatch(
    request: Request,
    id: UUID,
):
    """Delete a dispatch note."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.dispatch_handler(request)

    try:
        await handler.delete(DeleteDispatchCommand(id=id))
    except DispatchNotFoundException:
        raise HTTPException(status_code=404, detail="Dispatch not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to delete dispatch: {str(exc)}")

    return DeleteDispatchResponse(
        status=True,
        code=200,
        message="Dispatch deleted successfully",
    )

