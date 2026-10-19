"""
Item Master API Router

Provides REST APIs for managing Item Masters.

All list endpoints strictly conform to the standard response envelope format:
status, code, message, items, limit, offset, total, pages, next_page, has_more.

Python 3.13+
"""
import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.v1.schemas.item_master import (
    CreateItemMasterRequest,
    ItemMasterListResponse,
    ItemMasterSchema,
    ItemMasterSingleResponse,
    UpdateItemMasterRequest,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.masters.items.application.command import (
    CreateItemMasterCommand,
    DeleteItemMasterCommand,
    GetItemMasterQuery,
    ListItemMasterQuery,
    UpdateItemMasterCommand,
)
from app.modules.masters.items.domain.exceptions import (
    ItemCodeAlreadyExistsException,
    ItemNotFoundException,
)

router = APIRouter(
    prefix="/items",
    tags=["Item Master"],
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


def _dto_to_schema(dto) -> ItemMasterSchema:
    """Helper to convert ItemMasterDto to Pydantic ItemMasterSchema."""
    return ItemMasterSchema(
        id=str(dto.id),
        item_code=dto.item_code,
        item_name=dto.item_name,
        unit_id=str(dto.unit_id),
        rate=float(dto.rate),
        is_active=dto.is_active,
        owner_name=getattr(dto, "owner_name", None),
        can_modify=getattr(dto, "can_modify", True),
    )


# --- 1. List Item Masters ---

@router.get("", response_model=ItemMasterListResponse)
@router.get("/", response_model=ItemMasterListResponse)
@router.post("/list", response_model=ItemMasterListResponse)
async def list_items(
    request: Request,
    query: Optional[str] = Query(None, description="Search keyword by item name or code"),
    search: Optional[str] = Query(None, description="Alias for search query"),
    limit: int = Query(20, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Fetch list of Item Masters with search and pagination."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.item_master_handler(request)
    search_keyword = (query or search or "").strip()

    try:
        if search_keyword:
            total_count = await handler.count_search(keyword=search_keyword, owner=user_state)
        else:
            total_count = await handler.count(owner=user_state)

        # Calculate page from offset & limit
        page = (offset // max(1, limit)) + 1

        list_query = ListItemMasterQuery(
            page=page,
            size=limit,
            keyword=search_keyword if search_keyword else None,
            owner=user_state,
        )

        dtos = await handler.list(list_query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch item masters: {str(exc)}")

    items_schema = [_dto_to_schema(d) for d in dtos]
    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return ItemMasterListResponse(
        status=True,
        code=200,
        message="Item masters fetched successfully",
        items=items_schema,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
    )


# --- 2. Create Item Master ---

@router.post("", response_model=ItemMasterSingleResponse)
@router.post("/", response_model=ItemMasterSingleResponse)
async def create_item(
    request: Request,
    payload: CreateItemMasterRequest,
):
    """Create a new Item Master."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.item_master_handler(request)

    from decimal import Decimal
    command = CreateItemMasterCommand(
        item_code=payload.item_code,
        item_name=payload.item_name,
        unit_id=payload.unit_id,
        rate=Decimal(str(payload.rate)),
        created_by=user_state.id,
    )

    try:
        created_dto = await handler.create(command, owner=user_state)
    except ItemCodeAlreadyExistsException:
        raise HTTPException(status_code=400, detail="Item code already in use")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create item master: {str(exc)}")

    return ItemMasterSingleResponse(
        status=True,
        code=200,
        message="Item master created successfully",
        data=_dto_to_schema(created_dto),
    )


# --- 3. Get Single Item Master ---

@router.get("/{id}", response_model=ItemMasterSingleResponse)
async def get_item(
    request: Request,
    id: UUID,
):
    """Get single Item Master by UUID."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.item_master_handler(request)

    try:
        dto = await handler.get(GetItemMasterQuery(id=id, owner=user_state))
    except ItemNotFoundException:
        raise HTTPException(status_code=404, detail="Item master not found")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch item master: {str(exc)}")

    return ItemMasterSingleResponse(
        status=True,
        code=200,
        message="Item master fetched successfully",
        data=_dto_to_schema(dto),
    )


# --- 4. Update Item Master ---

@router.put("/{id}", response_model=ItemMasterSingleResponse)
async def update_item(
    request: Request,
    id: UUID,
    payload: UpdateItemMasterRequest,
):
    """Update an existing Item Master."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.item_master_handler(request)

    from decimal import Decimal
    command = UpdateItemMasterCommand(
        id=id,
        item_code=payload.item_code,
        item_name=payload.item_name,
        unit_id=payload.unit_id,
        rate=Decimal(str(payload.rate)),
        is_active=payload.is_active,
        owner=user_state,
    )

    try:
        updated_dto = await handler.update(command)
    except ItemNotFoundException:
        raise HTTPException(status_code=404, detail="Item master not found")
    except ItemCodeAlreadyExistsException:
        raise HTTPException(status_code=400, detail="Item code already in use")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to update item master: {str(exc)}")

    return ItemMasterSingleResponse(
        status=True,
        code=200,
        message="Item master updated successfully",
        data=_dto_to_schema(updated_dto),
    )


# --- 5. Delete Item Master ---

@router.delete("/{id}")
async def delete_item(
    request: Request,
    id: UUID,
):
    """Delete an Item Master."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.item_master_handler(request)

    try:
        await handler.delete(DeleteItemMasterCommand(id=id, owner=user_state))
    except ItemNotFoundException:
        raise HTTPException(status_code=404, detail="Item master not found")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to delete item master: {str(exc)}")

    return {
        "status": True,
        "code": 200,
        "message": "Item master deleted successfully",
    }
