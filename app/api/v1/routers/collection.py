"""
Collection API Router

Provides Milk Collections (Create, List Recent & Delete) for logged-in VLCC and MCC users.

Python 3.13+
"""
from app.api.v1.schemas.collection import (
    CollectionListResponse,
    DeleteCollectionsRequest,
    DeleteCollectionsResponse,
    BulkCreateCollectionResponse,
    CreateCollectionResponse,
    CreateCollectionRequest,
    InsertCollectionsRequest,
    CollectionResponseData,
    GetCollectionListRequest,
)



from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, Request
from sqlalchemy import select, or_, and_

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.collections.mcc_collection.domain.enums import (
    CollectionShift,
    MilkType,
    QuantityCollectionMode,
    MeasurementMode,
    CollectionStatus,
)
from app.modules.masters.advanced.domain.enums import PaymentMode
from app.modules.mcc.domain.enums import MccType

from app.modules.dependencies import GetHandler
from app.modules.collections.vlcc_collection.application.command import (
    CreateVlccCollectionCommand,
    DeleteVlccCollectionCommand,
    BulkDeleteVlccCollectionCommand,
)
from app.modules.collections.mcc_collection.application.command import (
    CreateMccCollectionCommand,
    DeleteMccCollectionCommand,
    BulkDeleteMccCollectionCommand,
)


router = APIRouter(
    prefix="/collections",
    tags=["Milk Collections"],
)


def format_shift_name(shift: Any) -> str:
    if shift is None:
        return "MORNING"
    if isinstance(shift, CollectionShift):
        return shift.name
    if isinstance(shift, int):
        try:
            return CollectionShift(shift).name
        except ValueError:
            return "MORNING" if shift == 0 else "EVENING"
    if hasattr(shift, 'name'):
        return str(shift.name)
    return str(shift)


def format_milk_type_name(milk_type: Any) -> str:
    if milk_type is None:
        return "MIXED"
    if isinstance(milk_type, MilkType):
        return milk_type.name
    if isinstance(milk_type, int):
        try:
            return MilkType(milk_type).name
        except ValueError:
            return "COW" if milk_type == 0 else ("BUFFALO" if milk_type == 1 else "MIXED")
    if hasattr(milk_type, 'name'):
        return str(milk_type.name)
    return str(milk_type)


def parse_shift_enum(shift: Any) -> CollectionShift | None:
    if shift is None or str(shift).upper().strip() in ("ALL", ""):
        return None
    val = str(shift).upper().strip()
    if val in ("0", "MORNING"):
        return CollectionShift.MORNING
    if val in ("1", "EVENING"):
        return CollectionShift.EVENING
    return None


def parse_milk_type_enum(milk_type: Any) -> MilkType | None:
    if milk_type is None or str(milk_type).upper().strip() in ("ALL", ""):
        return None
    val = str(milk_type).upper().strip()
    if val in ("0", "COW"):
        return MilkType.COW
    if val in ("1", "BUFFALO"):
        return MilkType.BUFFALO
    if val in ("2", "MIXED"):
        return MilkType.MIXED
    return None


def parse_qty_mode_enum(mode: Any) -> QuantityCollectionMode:
    if mode is None:
        return QuantityCollectionMode.MANUAL
    val = str(mode).upper().strip()
    if val in ("1", "AUTOMATIC", "AUTO"):
        return QuantityCollectionMode.AUTOMATIC
    return QuantityCollectionMode.MANUAL


def parse_measurement_mode_enum(mode: Any) -> MeasurementMode:
    if mode is None:
        return MeasurementMode.MANUAL
    val = str(mode).upper().strip()
    if val in ("1", "AUTOMATIC", "AUTO"):
        return MeasurementMode.AUTOMATIC
    return MeasurementMode.MANUAL


def parse_payment_mode_enum(mode: Any) -> PaymentMode:
    if mode is None:
        return PaymentMode.CASH
    val = str(mode).upper().strip()
    if val in ("2", "ONLINE"):
        return PaymentMode.ONLINE
    if val in ("3", "BANK_TRANSFER", "BANK"):
        return PaymentMode.BANK_TRANSFER
    if val in ("4", "UPI"):
        return PaymentMode.UPI
    if val in ("5", "CHEQUE"):
        return PaymentMode.CHEQUE
    return PaymentMode.CASH


def parse_status_enum(status: Any) -> CollectionStatus:
    if status is None:
        return CollectionStatus.UNPAID
    val = str(status).upper().strip()
    if val in ("1", "PAID"):
        return CollectionStatus.PAID
    return CollectionStatus.UNPAID


def parse_mcc_type_enum(mcc_type: Any) -> MccType:
    if mcc_type is None:
        return MccType.NORMAL
    if isinstance(mcc_type, MccType):
        return mcc_type
    val = str(mcc_type).upper().strip()
    if val in ("1", "FAT_SNF"):
        return MccType.FAT_SNF
    if val in ("2", "WEIGHT"):
        return MccType.WEIGHT
    if val in ("3", "FIXED_RATE"):
        return MccType.FIXED_RATE
    return MccType.NORMAL


def parse_date_bound(date_str: str | None, end_of_day: bool = False) -> datetime | None:
    if not date_str or not str(date_str).strip():
        return None
    val = str(date_str).strip()
    try:
        dt = datetime.fromisoformat(val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if end_of_day:
            return dt.replace(hour=23, minute=59, second=59)
        return dt
    except ValueError:
        pass
    try:
        d = datetime.strptime(val, "%Y-%m-%d")
        if end_of_day:
            return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)
        return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=timezone.utc)
    except ValueError:
        return None


# =========================================================
# SMART ENTITY RESOLVERS (UUID or CODE / INT)
# =========================================================

async def _create_a_vlcc_collection(request:Request, body: CreateCollectionRequest)-> CreateCollectionResponse:
    handler = GetHandler.vlcc_collection_handler(request)
    vlcc_id = UUID(str(body.collection_by))
    farmer_id = UUID(str(body.collection_to))

    command = CreateVlccCollectionCommand(
        vlcc_id=vlcc_id,
        farmer_id=farmer_id,
        collected_at=body.get_collected_at(),
        shift=body.shift,
        milk_type=body.milk_type,
        fat_percent=Decimal(str(body.fat_percent or 0.0)),
        snf_percent=Decimal(str(body.snf_percent or 0.0)),
        quantity=Decimal(str(body.quantity)),
        quantity_collection_mode=body.quantity_collection_mode,
        measurement_mode=body.measurement_mode,
        rate_per_unit=Decimal(str(body.rate_per_unit or 0.0)),
        total_amount=Decimal(str(body.total_amount or 0.0)),
        payment_mode=body.payment_mode,
        status=body.status,
    )

    result = await handler.create(command)

    created_item = CollectionResponseData(
        id=str(result.id),
        **body.model_dump()
    )
    return CreateCollectionResponse(
        status=True,
        message="VLCC milk collection recorded successfully",
        collection=created_item,
    )

async def _create_a_mcc_collection(request:Request, body: CreateCollectionRequest):
    handler = GetHandler.mcc_collection_handler(request)
    mcc_id = UUID(str(body.collection_by))
    vlcc_id = UUID(str(body.collection_to))

    command = CreateMccCollectionCommand(
        mcc_id=mcc_id,
        vlcc_id=vlcc_id,
        collected_at=body.get_collected_at(),
        shift=body.shift,
        milk_type=body.milk_type,
        mcc_type=body.mcc_type,
        fat_percent=Decimal(str(body.fat_percent or 0.0)),
        snf_percent=Decimal(str(body.snf_percent or 0.0)),
        clr_value=Decimal(str(body.clr_value or 0.0)),
        quantity=Decimal(str(body.quantity)),
        sample_number=body.sample_number,
        can_count=body.can_count,
        detection_value=Decimal(str(body.detection_value or 0.0)),
        calibration_fat=Decimal(str(body.calibration_fat or 0.0)),
        calibration_snf=Decimal(str(body.calibration_snf or 0.0)),
        rank=body.rank,
        quantity_collection_mode=body.quantity_collection_mode,
        measurement_mode=body.measurement_mode,
        rate_per_unit=Decimal(str(body.rate_per_unit or 0.0)),
        total_amount=Decimal(str(body.total_amount or 0.0)),
        payment_mode=body.payment_mode,
        status=body.status,
    )

    result = await handler.create(command)

    created_item = CollectionResponseData(
        id=str(result.id),
        **body.model_dump()
    )
    return CreateCollectionResponse(
        status=True,
        message="MCC milk collection recorded successfully",
        collection=created_item,
    )

async def _get_collection_by_vlcc(
    request: Request,
    currentUser: CurrentUser | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    shift: CollectionShift | None = None,
    offset: int = 0,
    limit: int = 20,
    vlcc_id: UUID | None = None,
    farmer_id: UUID | None = None,
    is_deleted: bool | None = None,
) -> CollectionListResponse:
    if not currentUser:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    handler = GetHandler.vlcc_collection_handler(request)
    detailed_list = await handler.get_detailed_collection_list(
        date_from=date_from,
        date_to=date_to,
        shift=shift,
        offset=offset,
        limit=limit,
        vlcc_id=vlcc_id,
        farmer_id=farmer_id,
        owner=currentUser,
        is_deleted=is_deleted,
    )
    total_count = await handler.get_total_collection_count(
        date_from=date_from,
        date_to=date_to,
        shift=shift,
        vlcc_id=vlcc_id,
        farmer_id=farmer_id,
        owner=currentUser,
        is_deleted=is_deleted,
    )

    items = [
        CollectionResponseData(
            id=str(dto.id),
            collection_by=str(dto.collection_by) if dto.collection_by else None,
            collection_to=str(dto.collection_to) if dto.collection_to else None,
            collected_at=dto.collected_at,
            member_code=dto.member_code,
            member_name=dto.member_name,
            role=dto.role,
            shift=dto.shift,
            milk_type=dto.milk_type,
            quantity=dto.quantity,
            quantity_collection_mode=dto.quantity_collection_mode,
            measurement_mode=dto.measurement_mode,
            fat_percent=dto.fat_percent,
            snf_percent=dto.snf_percent,
            clr_value=dto.clr_value,
            rate_per_unit=dto.rate_per_unit,
            total_amount=dto.total_amount,
            payment_mode=dto.payment_mode,
            status=dto.status,
            sample_number=dto.sample_number,
            can_count=dto.can_count,
            detection_value=dto.detection_value,
            mcc_type=dto.mcc_type,
            rank=dto.rank,
            calibration_fat=dto.calibration_fat,
            calibration_snf=dto.calibration_snf,
        )
        for dto in detailed_list
    ]

    pages = (total_count + limit - 1) // limit if limit > 0 and total_count > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1
    next_page = current_page + 1 if current_page < pages else None
    has_more = (offset + len(items)) < total_count

    return CollectionListResponse(
        status=True,
        code=200,
        message="VLCC milk collections fetched successfully",
        items=items,
        limit=limit,
        offset=offset,
        total=total_count,
        pages=pages,
        next_page=next_page,
        has_more=has_more,
    )


async def _get_collection_by_mcc(
    request: Request,
    currentUser: CurrentUser | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    shift: CollectionShift | None = None,
    offset: int = 0,
    limit: int = 20,
    mcc_id: UUID | None = None,
    vlcc_id: UUID | None = None,
    is_deleted: bool | None = None,
    exclude_zero_quality: bool = False,
) -> CollectionListResponse:
    if not currentUser:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.mcc_collection_handler(request)
    detailed_list = await handler.get_detailed_collection_list(
        date_from=date_from,
        date_to=date_to,
        shift=shift,
        offset=offset,
        limit=limit,
        mcc_id=mcc_id,
        vlcc_id=vlcc_id,
        owner=currentUser,
        is_deleted=is_deleted,
        exclude_zero_quality=exclude_zero_quality,
    )
    total_count = await handler.get_total_collection_count(
        date_from=date_from,
        date_to=date_to,
        shift=shift,
        mcc_id=mcc_id,
        vlcc_id=vlcc_id,
        owner=currentUser,
        is_deleted=is_deleted,
        exclude_zero_quality=exclude_zero_quality,
    )

    items = [
        CollectionResponseData(
            id=str(dto.id),
            collection_by=str(dto.collection_by) if dto.collection_by else None,
            collection_to=str(dto.collection_to) if dto.collection_to else None,
            collected_at=dto.collected_at,
            member_code=dto.member_code,
            member_name=dto.member_name,
            role=dto.role,
            shift=dto.shift,
            milk_type=dto.milk_type,
            quantity=dto.quantity,
            quantity_collection_mode=dto.quantity_collection_mode,
            measurement_mode=dto.measurement_mode,
            fat_percent=dto.fat_percent,
            snf_percent=dto.snf_percent,
            clr_value=dto.clr_value,
            rate_per_unit=dto.rate_per_unit,
            total_amount=dto.total_amount,
            payment_mode=dto.payment_mode,
            status=dto.status,
            sample_number=dto.sample_number,
            can_count=dto.can_count,
            detection_value=dto.detection_value,
            mcc_type=dto.mcc_type,
            rank=dto.rank,
            calibration_fat=dto.calibration_fat,
            calibration_snf=dto.calibration_snf,
        )
        for dto in detailed_list
    ]

    pages = (total_count + limit - 1) // limit if limit > 0 and total_count > 0 else 1
    current_page = (offset // limit) + 1 if limit > 0 else 1
    next_page = current_page + 1 if current_page < pages else None
    has_more = (offset + len(items)) < total_count

    return CollectionListResponse(
        status=True,
        code=200,
        message="MCC milk collections fetched successfully",
        items=items,
        limit=limit,
        offset=offset,
        total=total_count,
        pages=pages,
        next_page=next_page,
        has_more=has_more,
    )


# =========================================================
# CREATE COLLECTION API (VLCC or MCC)
# =========================================================

@router.post("", response_model=CreateCollectionResponse)
@router.post("/", response_model=CreateCollectionResponse)
async def create_collection(request: Request, body: CreateCollectionRequest):
    """
    Create a new Milk Collection Record.

    - **VLCC Role**: Accepts `farmer_id` (as UUID or farmer code like "1", "101").
    - **MCC Role**: Accepts `vlcc_id` (as UUID or VLCC code).
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    role_type = user_state.role_type

    # =====================================================
    # CREATE VLCC COLLECTION
    # =====================================================
    if role_type == Role.VLCC:
        try:
            result = await _create_a_vlcc_collection(request, body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return result

    # =====================================================
    # CREATE MCC COLLECTION
    # =====================================================
    elif role_type == Role.MCC:
        try:
            result = await _create_a_mcc_collection(request, body)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return result

    else:
        raise HTTPException(status_code=403, detail="Only VLCC or MCC users can record milk collections")


# =========================================================
# BULK CREATE COLLECTION API (VLCC or MCC)
# =========================================================

@router.post("/bulk", response_model=BulkCreateCollectionResponse)
@router.post("/bulk/", response_model=BulkCreateCollectionResponse)
async def create_bulk_collections(request: Request, data: InsertCollectionsRequest):
    """
    Create multiple Milk Collection Records in Bulk.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    role_type = user_state.role_type

    # One record maker per role; reject any other role up front.
    if role_type == Role.VLCC:
        create_one = _create_a_vlcc_collection
        label = "VLCC"
    elif role_type == Role.MCC:
        create_one = _create_a_mcc_collection
        label = "MCC"
    else:
        raise HTTPException(status_code=403, detail="Only VLCC or MCC users can record milk collections")

    if not data.items:
        raise HTTPException(status_code=400, detail="No collection items were provided.")

    created_items: List[CollectionResponseData] = []

    # =====================================================
    # ALL-OR-NOTHING: the whole batch is one transaction.
    # Each record runs on a savepoint inside it; the first failure
    # aborts everything so nothing is half-saved.
    # =====================================================
    database = request.app.state.application.container.database
    try:
        async with database.transaction():
            for index, body in enumerate(data.items):
                try:
                    result = await create_one(request, body)
                except Exception as exc:
                    # Point at the offending row; rolls back the whole batch.
                    raise HTTPException(
                        status_code=400,
                        detail=f"{label} bulk collection failed at item {index + 1}: {exc}. Nothing was saved.",
                    ) from exc
                created_items.append(result.collection)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{label} bulk collection failed: {exc}. Nothing was saved.",
        ) from exc

    return BulkCreateCollectionResponse(
        status=True,
        code=200,
        message=f"{label} bulk milk collections recorded successfully",
        created_count=len(created_items),
        collections=created_items,
    )


# =========================================================
# RECENT / LIST COLLECTIONS API (VLCC, MCC & FARMER)
# =========================================================

@router.post("", response_model=CollectionListResponse)
@router.post("/", response_model=CollectionListResponse)
@router.post("/recent", response_model=CollectionListResponse)
@router.post("/recent/", response_model=CollectionListResponse)
@router.post("/list", response_model=CollectionListResponse)
@router.post("/list/", response_model=CollectionListResponse)
async def get_recent_collections(
    request: Request,
    body: GetCollectionListRequest = Body(default_factory=GetCollectionListRequest),
):
    """
    Get Milk Collections for Logged-In User (VLCC, MCC & FARMER) via POST.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    shift_filter = parse_shift_enum(body.shift)
    dt_from = parse_date_bound(body.date_from, end_of_day=False)
    dt_to = parse_date_bound(body.date_to, end_of_day=True)

    member_id_uuid: UUID | None = None
    if body.member_id:
        try:
            member_id_uuid = UUID(str(body.member_id))
        except ValueError:
            pass

    role_type = user_state.role_type

    if role_type == Role.MCC:
        return await _get_collection_by_mcc(
            request=request,
            currentUser=user_state,
            date_from=dt_from,
            date_to=dt_to,
            shift=shift_filter,
            offset=body.offset,
            limit=body.limit,
            is_deleted=body.is_deleted,
            mcc_id=user_state.own_id,
            vlcc_id=member_id_uuid,
        )
    elif role_type == Role.VLCC:
        return await _get_collection_by_vlcc(
            request=request,
            currentUser=user_state,
            date_from=dt_from,
            date_to=dt_to,
            shift=shift_filter,
            offset=body.offset,
            limit=body.limit,
            is_deleted=body.is_deleted,
            vlcc_id=user_state.own_id,
            farmer_id=member_id_uuid,
        )
    elif role_type == Role.VLCC_FARMER:
        return await _get_collection_by_mcc(
            request=request,
            currentUser=user_state,
            date_from=dt_from,
            date_to=dt_to,
            shift=shift_filter,
            offset=body.offset,
            limit=body.limit,
            is_deleted=body.is_deleted,
            vlcc_id=user_state.own_id,
            exclude_zero_quality=True,
        )
    elif role_type == Role.FARMER:
        return await _get_collection_by_vlcc(
            request=request,
            currentUser=user_state,
            date_from=dt_from,
            date_to=dt_to,
            shift=shift_filter,
            offset=body.offset,
            limit=body.limit,
            is_deleted=body.is_deleted,
            farmer_id=user_state.own_id,
        )
    else:
        return await _get_collection_by_vlcc(
            request=request,
            currentUser=user_state,
            date_from=dt_from,
            date_to=dt_to,
            shift=shift_filter,
            offset=body.offset,
            limit=body.limit,
            is_deleted=body.is_deleted,
            farmer_id=user_state.own_id,
        )






# =========================================================
# DELETE COLLECTION API (SINGLE & BULK)
# =========================================================

@router.delete("/bulk", response_model=DeleteCollectionsResponse)
@router.delete("/bulk/", response_model=DeleteCollectionsResponse)
@router.post("/delete-bulk", response_model=DeleteCollectionsResponse)
@router.post("/delete-bulk/", response_model=DeleteCollectionsResponse)
@router.delete("", response_model=DeleteCollectionsResponse)
@router.delete("/", response_model=DeleteCollectionsResponse)
async def delete_collections(
    request: Request,
    body: DeleteCollectionsRequest = Body(default_factory=DeleteCollectionsRequest),
):
    """
    Bulk delete milk collection records by list of UUIDs.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not body.ids:
        return DeleteCollectionsResponse(
            status=True,
            message="No collection IDs provided for deletion",
            deleted_ids=[],
        )

    uuids: list[UUID] = []
    for raw_id in body.ids:
        try:
            uuids.append(UUID(str(raw_id)))
        except ValueError:
            pass

    if not uuids:
        raise HTTPException(status_code=400, detail="Invalid collection UUID format")

    deleted_uuids: list[UUID] = []
    role_type = user_state.role_type

    if role_type == Role.MCC:
        mcc_handler = GetHandler.mcc_collection_handler(request)
        cmd = BulkDeleteMccCollectionCommand(ids=uuids)
        deleted_uuids = await mcc_handler.delete_bulk(cmd, user_state)
    else:
        vlcc_handler = GetHandler.vlcc_collection_handler(request)
        vlcc_deleted = await vlcc_handler.delete_bulk(uuids, user_state)
        deleted_uuids.extend(vlcc_deleted)

    remaining_uuids = [u for u in uuids if u not in vlcc_deleted]

    deleted_str_ids = [str(uid) for uid in deleted_uuids]
    failed_str_ids = [str(uid) for uid in remaining_uuids]

    return DeleteCollectionsResponse(
        status=True,
        message=f"{len(deleted_str_ids)} milk collection record(s) deleted successfully",
        deleted_ids=deleted_str_ids,
        failed_ids=failed_str_ids,
    )


@router.delete("/{collection_id}", response_model=DeleteCollectionsResponse)
@router.delete("/{collection_id}/", response_model=DeleteCollectionsResponse)
async def delete_collection(request: Request, collection_id: str):
    """
    Delete a single Milk Collection Record by UUID.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        col_uuid = UUID(str(collection_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid collection UUID format")

    role_type = user_state.role_type
    deleted = False

    if role_type == Role.MCC:
        mcc_handler = GetHandler.mcc_collection_handler(request)
        cmd = DeleteMccCollectionCommand(id=col_uuid)
        await mcc_handler.delete(cmd, user_state)
        deleted = True
    elif role_type in (Role.VLCC, Role.FARMER):
        vlcc_handler = GetHandler.vlcc_collection_handler(request)
        cmd = DeleteVlccCollectionCommand(id=col_uuid)
        await vlcc_handler.delete(cmd, user_state)
        deleted = True
    else:
        vlcc_handler = GetHandler.vlcc_collection_handler(request)
        vlcc_deleted = await vlcc_handler.delete_bulk([col_uuid], user_state)
        if vlcc_deleted:
            deleted = True
        else:
            mcc_handler = GetHandler.mcc_collection_handler(request)
            mcc_deleted = await mcc_handler.delete_bulk([col_uuid], user_state)
            if mcc_deleted:
                deleted = True

    if not deleted:
        raise HTTPException(status_code=404, detail="Collection record not found or unauthorized")

    return DeleteCollectionsResponse(
        status=True,
        message="Milk collection record deleted successfully",
        deleted_ids=[str(col_uuid)],
    )

