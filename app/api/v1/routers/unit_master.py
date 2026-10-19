"""
Unit Master API Router

Provides REST APIs for managing Unit Masters.

All list endpoints strictly conform to the standard response envelope format:
status, code, message, items, limit, offset, total, pages, next_page, has_more.

Python 3.13+
"""
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.v1.schemas.unit_master import (
    CreateUnitMasterRequest,
    UnitMasterListResponse,
    UnitMasterSchema,
    UnitMasterSingleResponse,
    UpdateUnitMasterRequest,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.masters.units.application.command import (
    CreateUnitMasterCommand,
    DeleteUnitMasterCommand,
    GetUnitMasterQuery,
    ListUnitMasterQuery,
    UpdateUnitMasterCommand,
)
from app.modules.masters.units.domain.exceptions import (
    UnitAlreadyExistsException,
    UnitNotFoundException,
)

router = APIRouter(
    prefix="/units",
    tags=["Unit Master"],
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


def _dto_to_schema(dto) -> UnitMasterSchema:
    """Helper to convert UnitMasterDto / UnitMasterListDto to Pydantic UnitMasterSchema."""
    return UnitMasterSchema(
        id=str(dto.id),
        name=dto.name,
        is_active=dto.is_active,
        owner_name=getattr(dto, "owner_name", None),
        can_modify=getattr(dto, "can_modify", True),
    )


# --- 1. List Unit Masters ---

@router.get("", response_model=UnitMasterListResponse)
@router.get("/", response_model=UnitMasterListResponse)
@router.post("/list", response_model=UnitMasterListResponse)
async def list_units(
    request: Request,
    query: Optional[str] = Query(None, description="Search keyword by unit name"),
    search: Optional[str] = Query(None, description="Alias for search query"),
    limit: int = Query(20, ge=1, le=500, description="Units per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Fetch list of Unit Masters with search and pagination."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.unit_master_handler(request)
    search_keyword = (query or search or "").strip()

    try:
        if search_keyword:
            total_count = await handler.count_search(keyword=search_keyword, owner=user_state)
        else:
            total_count = await handler.count(owner=user_state)

        # Calculate page from offset & limit
        page = (offset // max(1, limit)) + 1

        list_query = ListUnitMasterQuery(
            page=page,
            size=limit,
            keyword=search_keyword if search_keyword else None,
            owner=user_state,
        )

        dtos = await handler.list(list_query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch unit masters: {str(exc)}")

    items_schema = [_dto_to_schema(d) for d in dtos]
    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return UnitMasterListResponse(
        status=True,
        code=200,
        message="Unit masters fetched successfully",
        items=items_schema,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
    )


# --- 2. Create Unit Master ---

@router.post("", response_model=UnitMasterSingleResponse)
@router.post("/", response_model=UnitMasterSingleResponse)
async def create_unit(
    request: Request,
    payload: CreateUnitMasterRequest,
):
    """Create a new Unit Master."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.unit_master_handler(request)

    command = CreateUnitMasterCommand(
        name=payload.name,
        created_by=user_state.id,
    )

    try:
        created_dto = await handler.create(command, owner=user_state)
    except UnitAlreadyExistsException:
        raise HTTPException(status_code=400, detail="Unit name already exists")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create unit master: {str(exc)}")

    return UnitMasterSingleResponse(
        status=True,
        code=200,
        message="Unit master created successfully",
        data=_dto_to_schema(created_dto),
    )


# --- 3. Get Single Unit Master ---

@router.get("/{id}", response_model=UnitMasterSingleResponse)
async def get_unit(
    request: Request,
    id: UUID,
):
    """Get single Unit Master by UUID."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.unit_master_handler(request)

    try:
        dto = await handler.get(GetUnitMasterQuery(id=id, owner=user_state))
    except UnitNotFoundException:
        raise HTTPException(status_code=404, detail="Unit master not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch unit master: {str(exc)}")

    return UnitMasterSingleResponse(
        status=True,
        code=200,
        message="Unit master fetched successfully",
        data=_dto_to_schema(dto),
    )


# --- 4. Update Unit Master ---

@router.put("/{id}", response_model=UnitMasterSingleResponse)
async def update_unit(
    request: Request,
    id: UUID,
    payload: UpdateUnitMasterRequest,
):
    """Update an existing Unit Master."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.unit_master_handler(request)

    command = UpdateUnitMasterCommand(
        id=id,
        name=payload.name,
        is_active=payload.is_active,
        owner=user_state,
    )

    try:
        updated_dto = await handler.update(command)
    except UnitNotFoundException:
        raise HTTPException(status_code=404, detail="Unit master not found")
    except UnitAlreadyExistsException:
        raise HTTPException(status_code=400, detail="Unit name already exists")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to update unit master: {str(exc)}")

    return UnitMasterSingleResponse(
        status=True,
        code=200,
        message="Unit master updated successfully",
        data=_dto_to_schema(updated_dto),
    )


# --- 5. Delete Unit Master ---

@router.delete("/{id}")
async def delete_unit(
    request: Request,
    id: UUID,
):
    """Delete a Unit Master."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.unit_master_handler(request)

    try:
        await handler.delete(DeleteUnitMasterCommand(id=id, owner=user_state))
    except UnitNotFoundException:
        raise HTTPException(status_code=404, detail="Unit master not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to delete unit master: {str(exc)}")

    return {
        "status": True,
        "code": 200,
        "message": "Unit master deleted successfully",
    }
