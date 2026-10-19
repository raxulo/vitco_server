"""
VLCC API Router

Python 3.13+
"""
from __future__ import annotations

from typing import Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.api.v1.schemas.vlcc import (
    VlccDetailResponse,
    VlccItemResponse,
    VlccListResponse,
    UpdateVlccRequest,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.vlcc.application.command import GetVlccQuery, ListVlccQuery
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.common.settings.infrastructure.models import SettingsModel

router = APIRouter(
    prefix="/vlcc",
    tags=["VLCC Master"],
)


@router.get("", response_model=VlccListResponse)
@router.get("/", response_model=VlccListResponse)
async def list_vlccs(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=500, description="Page size"),
    search: str | None = Query(default=None, description="Search keyword"),
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    query = ListVlccQuery(
        page=page,
        size=size,
        keyword=search,
        owner=user,
    )
    items = await GetHandler.vlcc_handler(request).list(query=query)
    total = await GetHandler.vlcc_handler(request).count(search, owner=user)
    total_pages = (total + size - 1) // size if total > 0 else 1

    return VlccListResponse(
        items=[VlccItemResponse.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{vlcc_id}", response_model=VlccDetailResponse)
async def get_vlcc(
    request: Request,
    vlcc_id: UUID,
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        query = GetVlccQuery(id=vlcc_id, owner=user)
        detail = await GetHandler.vlcc_handler(request).get_full_detail(query=query)
        if not detail or not detail.vlcc:
            raise HTTPException(status_code=404, detail="VLCC not found")
        return VlccDetailResponse.model_validate(detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"VLCC not found: {str(e)}")


@router.put("", response_model=VlccDetailResponse)
@router.put("/", response_model=VlccDetailResponse)
@router.put("/me", response_model=VlccDetailResponse)
@router.put("/settings", response_model=VlccDetailResponse)
async def update_vlcc(
    request: Request,
    body: UpdateVlccRequest,
):
    """
    Update VLCC Profile Details and Settings.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session

    stmt = select(VlccModel).where((VlccModel.user_id == user.id) | (VlccModel.created_by == user.id))
    res = await session.execute(stmt)
    vlcc_obj = res.scalar_one_or_none()

    if not vlcc_obj:
        raise HTTPException(status_code=444, detail="VLCC profile not found")

    data = body.model_dump(exclude_unset=True)
    settings_data = data.pop("settings", None)

    for key, value in data.items():
        if hasattr(vlcc_obj, key) and value is not None:
            setattr(vlcc_obj, key, value)

    if settings_data:
        if not vlcc_obj.settings_id:
            settings_obj = SettingsModel()
            session.add(settings_obj)
            await session.flush()
            vlcc_obj.settings_id = settings_obj.id
        else:
            settings_obj = await session.get(SettingsModel, vlcc_obj.settings_id)

        if settings_obj:
            for key, value in settings_data.items():
                if hasattr(settings_obj, key) and value is not None:
                    setattr(settings_obj, key, value)

    await session.flush()

    query = GetVlccQuery(id=vlcc_obj.id, owner=user)
    detail = await GetHandler.vlcc_handler(request).get_full_detail(query=query)
    return VlccDetailResponse.model_validate(detail)
