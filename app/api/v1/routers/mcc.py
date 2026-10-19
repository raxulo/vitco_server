"""
MCC API Router

Python 3.13+
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID
from fastapi import APIRouter, Body, HTTPException, Query, Request
from sqlalchemy import select

from app.api.v1.schemas.mcc import (
    MccDetailResponse,
    MccItemResponse,
    MccListResponse,
    UpdateMccRequest,
    MccSampleResultResponse,
    MccCollectionBySampleResponse,
    MccSampleCollectionDetail,
    MccSampleInfo,
    GetNextSampleNumberRequest,
    GetCollectionBySampleNumberRequest,
    CheckSampleNumberExistsResponse,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.mcc.application.command import GetMccQuery, ListMccQuery
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.application.command import (
    GetNextSampleNumberQuery,
    GetCollectionBySampleNumberQuery,
)

router = APIRouter(
    prefix="/mccs",
    tags=["MCC Master"],
)

@router.get("", response_model=MccListResponse)
@router.get("/", response_model=MccListResponse)
async def list_mccs(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=500, description="Page size"),
    search: str | None = Query(default=None, description="Search keyword"),
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    query = ListMccQuery(
        page=page,
        size=size,
        keyword=search,
        owner=user,
    )
    items = await GetHandler.mcc_handler(request).list(query=query)
    total = await GetHandler.mcc_handler(request).count(search, owner=user)
    total_pages = (total + size - 1) // size if total > 0 else 1

    return MccListResponse(
        items=[MccItemResponse.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


# =============================================================================
# Helpers
# =============================================================================

def _parse_shift(shift: Any) -> CollectionShift:
    if isinstance(shift, CollectionShift):
        return shift
    if shift is None:
        return CollectionShift.MORNING
    val = str(shift).upper().strip()
    if val in ("1", "EVENING"):
        return CollectionShift.EVENING
    return CollectionShift.MORNING


def _parse_collected_at(val: str | datetime | None) -> datetime:
    if val is None:
        return datetime.now()
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    if not s:
        return datetime.now()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(s.split(".")[0], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now()


async def _resolve_mcc_id(request: Request, user: CurrentUser, mcc_id: UUID | None) -> UUID:
    if mcc_id:
        return mcc_id
    if user.own_id:
        return user.own_id
    session = request.app.state.application.container.database.session
    stmt = (
        select(MccModel.id)
        .where((MccModel.user_id == user.id) | (MccModel.created_by == user.id))
        .limit(1)
    )
    res = await session.execute(stmt)
    found_id = res.scalar_one_or_none()
    if found_id:
        return found_id
    raise HTTPException(
        status_code=400,
        detail="mcc_id is required or logged-in user is not linked to any MCC profile",
    )


# =============================================================================
# Next Sample Number Endpoints
# =============================================================================
@router.post(
    "/genext-sample-number",
    response_model=MccSampleResultResponse,
    operation_id="post_mcc_genext_sample_number_dash",
)
@router.post(
    "/next-sample-number",
    response_model=MccSampleResultResponse,
    operation_id="post_mcc_next_sample_number",
)
async def get_genext_sample_number(
    request: Request,
    body: GetNextSampleNumberRequest = Body(default_factory=GetNextSampleNumberRequest),
):
    """
    Get Next Sample Number for MCC collection.
    Data is retrieved via MccCollectionHandler.genext_sample_number.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    parsed_shift = _parse_shift(body.shift)
    parsed_date = _parse_collected_at(body.collected_at)

    query = GetNextSampleNumberQuery(
        mcc_id=user.own_id,
        shift=parsed_shift,
        collected_at=parsed_date,
    )
    result = await GetHandler.mcc_collection_handler(request).genext_sample_number(query=query)
    return MccSampleResultResponse(
        sample_start=result.sample_start,
        sample_end=result.sample_end,
        is_mcc_exists=result.is_mcc_exists,
        next_sample_number=result.next_sample_number,
        range=result.range,
        out_of_range=result.out_of_range,
        is_ok=result.is_ok,
    )




# =============================================================================
# Collection by Sample Number Endpoints
# =============================================================================

@router.post(
    "/collection-by-sample-result",
    operation_id="post_mcc_collection_by_sample_result_dash",
)
@router.post(
    "/collection_by_sample_result",
    operation_id="post_mcc_collection_by_sample_result_underscore",
)
async def get_collection_by_sample_result(
    request: Request,
    body: GetCollectionBySampleNumberRequest = Body(...),
    raise_if_not_found: bool = Query(default=True, description="Raise 404 if collection not found"),
):
    """
    Get MCC Collection by Sample Number.
    Data is retrieved via MccCollectionHandler.collection_by_sample_result.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    parsed_shift = _parse_shift(body.shift)
    parsed_date = _parse_collected_at(body.collected_at)

    

    query = GetCollectionBySampleNumberQuery(
        mcc_id=user.own_id,
        sample_number=body.sample_number,
        shift=parsed_shift,
        collected_at=parsed_date,
    )
    is_collected = await GetHandler.mcc_collection_handler(request).is_sample_number_collected(
        query=query
    )
    if is_collected:
        return MccCollectionBySampleResponse(
            info=MccSampleInfo(
                mcc_id=user.own_id,
                sample_number=body.sample_number,
                shift=parsed_shift.value if hasattr(parsed_shift, "value") else parsed_shift,
                collection_status="Already taken",
                status_code=400,
                status="error",
            ),
            collection_detail=None,
        )

    result = await GetHandler.mcc_collection_handler(request).collection_by_sample_result(query=query)

    if not result:
        if raise_if_not_found:
            raise HTTPException(
                status_code=404,
                detail=f"Sample number not exits.",
            )
        return None

    return MccCollectionBySampleResponse(
        info=None,
        collection_detail=MccSampleCollectionDetail(
            mcc_id=result.mcc_id,
            mcc_name=result.mcc_name,
            collection_id=result.collection_id,
            quantity=float(result.quantity) if result.quantity else 0.0,
            can_count=result.can_count,
            vlcc_id=result.vlcc_id,
            vlcc_name=result.vlcc_name,
            is_deleted=result.is_deleted,
            quantity_collection_mode=result.quantity_collection_mode,
        ),
    )


@router.get("/{mcc_id}", response_model=MccDetailResponse)
async def get_mcc(
    request: Request,
    mcc_id: UUID,
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        query = GetMccQuery(id=mcc_id, owner=user)
        detail = await GetHandler.mcc_handler(request).get_full_detail(query=query)
        if not detail or not detail.mcc:
            raise HTTPException(status_code=404, detail="MCC not found")
        return MccDetailResponse.model_validate(detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"MCC not found: {str(e)}")


@router.put("", response_model=MccDetailResponse)
@router.put("/", response_model=MccDetailResponse)
@router.put("/me", response_model=MccDetailResponse)
@router.put("/settings", response_model=MccDetailResponse)
async def update_mcc(
    request: Request,
    body: UpdateMccRequest,
):
    """
    Update MCC Profile Details and Settings.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session

    stmt = select(MccModel).where((MccModel.user_id == user.id) | (MccModel.created_by == user.id))
    res = await session.execute(stmt)
    mcc_obj = res.scalar_one_or_none()

    if not mcc_obj:
        raise HTTPException(status_code=444, detail="MCC profile not found")

    data = body.model_dump(exclude_unset=True)
    settings_data = data.pop("settings", None)

    for key, value in data.items():
        if hasattr(mcc_obj, key) and value is not None:
            setattr(mcc_obj, key, value)

    if settings_data:
        if not mcc_obj.settings_id:
            settings_obj = SettingsModel()
            session.add(settings_obj)
            await session.flush()
            mcc_obj.settings_id = settings_obj.id
        else:
            settings_obj = await session.get(SettingsModel, mcc_obj.settings_id)

        if settings_obj:
            for key, value in settings_data.items():
                if hasattr(settings_obj, key) and value is not None:
                    setattr(settings_obj, key, value)

    await session.flush()

    query = GetMccQuery(id=mcc_obj.id, owner=user)
    detail = await GetHandler.mcc_handler(request).get_full_detail(query=query)
    return MccDetailResponse.model_validate(detail)
