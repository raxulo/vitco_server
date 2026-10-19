"""
Members (Farmers) API Router

Handles Member creation, updates, deletion, code checks, and retrieval.
Authorization:
- Strictly restricted: Only authenticated VLCC users (Role.VLCC) can create, update, or delete members.
- Center Scoping: Operations are strictly isolated to the authenticated VLCC user's center.
- Entity Guard: Only Farmer role records can be created, updated, or deleted.

Python 3.13+
"""
from app.core.exceptions.base import ApplicationException
import math
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select

from app.api.v1.schemas.farmer import (
    CheckCodeRequest,
    CheckCodeResponse,
    CreateFarmerApiRequest,
    DeleteFarmerResponse,
    FarmerDtoResponse,
    FarmerItemResponse,
    FarmerListResponse,
    UpdateFarmerApiRequest,
)
from app.api.v1.schemas.sync import SubUserProfileSyncDto
from app.middleware.authentication import CurrentUser
from app.modules.administration.application.command import CreateUserCommand, UserData
from app.modules.administration.domain.enums import Role
from app.modules.common.address.application.command import AddressData, CreateAddressCommand
from app.modules.common.bank.application.command import BankAccountData, CreateBankAccountCommand
from app.modules.dependencies import GetHandler
from app.modules.farmer.application.command import (
    CreateFarmerCommand,
    CreateFarmerDetailCommand,
    DeleteFarmerCommand,
    ListFarmerQuery,
    UpdateFarmerCommand,
    UpdateFarmerDetailCommand,
)
from app.modules.farmer.domain.dto import FarmerFullDetailDto
from app.modules.farmer.domain.enums import MilkType
from app.modules.farmer.domain.exceptions import (
    FarmerCodeAlreadyExistsException,
    FarmerNotFoundException,
)
from app.modules.vlcc.infrastructure.models import VlccModel

router = APIRouter(
    tags=["Members (Farmers)"],
)


async def _resolve_vlcc(session, user: CurrentUser) -> VlccModel:
    """
    Resolve and enforce the authenticated VLCC user's center model.
    Raises HTTP 403 Forbidden if user does not possess Role.VLCC.
    """
    if user.role_type != Role.VLCC:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only VLCC users are authorized to create, update, or delete members.",
        )

    stmt = select(VlccModel).where(
        (VlccModel.id == user.own_id) if user.own_id else (
            (VlccModel.user_id == user.id) | (VlccModel.created_by == user.id)
        )
    )
    res = await session.execute(stmt)
    vlcc = res.scalar_one_or_none()

    if not vlcc:
        raise HTTPException(
            status_code=400,
            detail="No VLCC center found for the authenticated user.",
        )
    return vlcc


async def _resolve_vlcc_id(session, user: CurrentUser) -> UUID:
    vlcc = await _resolve_vlcc(session, user)
    return vlcc.id


def farmer_full_detail_to_sub_user_sync_dto(
    detail: FarmerFullDetailDto,
) -> SubUserProfileSyncDto:
    """
    Convert FarmerFullDetailDto to SubUserProfileSyncDto.
    """
    f = detail.farmer
    u = detail.user
    rate_chart_val = f.assigned_chart_rank if f.assigned_chart_rank is not None else 1
    return SubUserProfileSyncDto(
        id=f.id,
        user_id=f.user_id,
        code=f.farmer_code,
        name=f.name or u.name,
        email=u.email,
        mobile=u.mobile,
        role=Role.FARMER,
        profile_image=f.profile_image or u.profile_image,
        uic_code=None,
        milk_type=f.milk_type,
        assigned_chart_rank=rate_chart_val,
        can_modify=f.can_modify,
        address=detail.address,
        bank_account=detail.bank_account,
        status=True,
    )


# Function aliases
farmer_to_sub_user_profile_sync_dto = farmer_full_detail_to_sub_user_sync_dto
_to_sub_user_profile_sync_dto = farmer_full_detail_to_sub_user_sync_dto


def _to_farmer_dto_response(
    detail: FarmerFullDetailDto,
    status: bool = True,
    code: int = 200,
    message: str = "Operation completed successfully",
) -> FarmerDtoResponse:
    """
    Construct standardized FarmerDtoResponse adhering to AGENTS.md response envelopes
    directly from FarmerFullDetailDto without boilerplate.
    """
    f = detail.farmer
    res = FarmerDtoResponse(
        status=status,
        code=code,
        message=message,
        id=f.id,
        user_id=f.user_id,
        farmer_code=f.farmer_code,
        name=f.name,
        milk_type=f.milk_type,
        vlcc_id=f.vlcc_id,
        vlcc_name=f.vlcc_name,
        address_id=f.address_id,
        bank_account_id=f.bank_account_id,
        assigned_chart_rank=f.assigned_chart_rank if f.assigned_chart_rank is not None else 1,
        profile_image=f.profile_image or (detail.user.profile_image if detail.user else None),
        sms_enabled=f.sms_enabled,
        is_active=f.is_active,
        can_modify=f.can_modify,
        user=detail.user,
        address=detail.address,
        bank_account=detail.bank_account,
    )
    res.data = res.model_dump(exclude={"status", "code", "message", "data"})
    return res


@router.get("", response_model=FarmerListResponse)
@router.get("/", response_model=FarmerListResponse)
async def list_farmers(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=500, description="Page size"),
    search: str | None = Query(default=None, description="Search keyword"),
    vlcc_id: UUID | None = Query(default=None, description="Filter by VLCC ID"),
):
    """
    List members/farmers with pagination and search.
    If authenticated as VLCC, automatically scoped to the caller's VLCC center.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    handler = GetHandler.farmer_handler(request)

    effective_vlcc_id = vlcc_id
    current_vlcc = None
    if user.role_type == Role.VLCC:
        current_vlcc = await _resolve_vlcc(session, user)
        effective_vlcc_id = current_vlcc.id

    keyword = search.strip() if search and search.strip() else None

    if keyword:
        total = await handler.count_search(keyword=keyword, vlcc_id=effective_vlcc_id, owner=user)
    else:
        total = await handler.count(vlcc_id=effective_vlcc_id, owner=user)

    offset = (page - 1) * size
    limit = size
    pages = math.ceil(total / limit) if total > 0 else 1
    next_page = page + 1 if page < pages else None
    has_more = page < pages

    query = ListFarmerQuery(
        keyword=keyword,
        vlcc_id=effective_vlcc_id,
        offset=offset,
        limit=limit,
        owner=user,
    )
    items = await handler.list(query=query)

    is_vlcc = user.role_type == Role.VLCC
    farmer_perm_enabled = current_vlcc.farmer_enabled if (is_vlcc and current_vlcc) else False
    item_responses: list[FarmerItemResponse] = []
    for item in items:
        item_obj = FarmerItemResponse.model_validate(item)
        item_obj.can_modify = (
            is_vlcc
            and farmer_perm_enabled
            and (item.vlcc_id == effective_vlcc_id)
            and getattr(item, "can_modify", True)
        )
        item_responses.append(item_obj)

    return FarmerListResponse(
        status=True,
        code=200,
        message="Members fetched successfully",
        items=item_responses,
        page=page,
        size=size,
        total=total,
        total_pages=pages,
        limit=limit,
        offset=offset,
        pages=pages,
        next_page=next_page,
        has_more=has_more,
    )


@router.get("/check-code", response_model=CheckCodeResponse)
@router.get("/check-code/", response_model=CheckCodeResponse)
@router.post("/check-code", response_model=CheckCodeResponse)
@router.post("/check-code/", response_model=CheckCodeResponse)
async def check_farmer_code(
    request: Request,
    code: str | None = Query(default=None, description="Farmer code"),
    farmer_code: str | None = Query(default=None, description="Farmer code alias"),
    vlcc_id: UUID | None = Query(default=None, description="VLCC ID"),
    body: CheckCodeRequest | None = None,
):
    """
    Check if a farmer code is already registered in the VLCC center.
    Strictly restricted: Only authenticated VLCC users can check member codes.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    vlcc = await _resolve_vlcc(session, user)
    if not vlcc.farmer_enabled:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Farmer permission is disabled for this VLCC center.",
        )
    effective_vlcc_id = vlcc.id

    target_code = code or farmer_code
    if body and not target_code:
        target_code = body.code or body.farmer_code

    if not target_code or not target_code.strip():
        raise HTTPException(status_code=400, detail="Farmer code is required")

    handler = GetHandler.farmer_handler(request)
    exists = await handler._farmer_repository.exists_code_in_vlcc(
        farmer_code=target_code.strip(),
        vlcc_id=effective_vlcc_id,
        owner=user,
    )

    return CheckCodeResponse(
        exists=exists,
        available=not exists,
        farmer_code=target_code.strip(),
        vlcc_id=str(effective_vlcc_id),
        message="already in use" if exists else "available",
    )


@router.get("/by-code/{farmer_code}", response_model=SubUserProfileSyncDto)
@router.get("/by-code/{farmer_code}/", response_model=SubUserProfileSyncDto)
async def get_farmer_by_code(
    request: Request,
    farmer_code: str,
) -> SubUserProfileSyncDto:
    """
    Fetch a single Member (Farmer) by Farmer Code in the authenticated VLCC center.
    Uses get_full_detail_by_code to retrieve all joined profile data in a single query.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    effective_vlcc_id = await _resolve_vlcc_id(session, user)

    handler = GetHandler.farmer_handler(request)
    detail = await handler.get_full_detail_by_code(farmer_code, effective_vlcc_id, owner=user)
    if not detail:
        raise HTTPException(status_code=404, detail="Member not found")

    return farmer_full_detail_to_sub_user_sync_dto(detail)


@router.get("/{farmer_id}", response_model=SubUserProfileSyncDto)
@router.get("/{farmer_id}/", response_model=SubUserProfileSyncDto)
async def get_farmer(
    request: Request,
    farmer_id: UUID,
) -> SubUserProfileSyncDto:
    """
    Fetch a single Member (Farmer) by UUID.
    Uses get_full_detail to retrieve all joined profile data in a single query.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    effective_vlcc_id = await _resolve_vlcc_id(session, user)

    handler = GetHandler.farmer_handler(request)
    detail = await handler.get_full_detail(farmer_id, owner=user)
    if not detail:
        raise HTTPException(status_code=404, detail="Member not found")

    if detail.farmer.vlcc_id != effective_vlcc_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You can only access members belonging to your own VLCC center.",
        )

    return farmer_full_detail_to_sub_user_sync_dto(detail)


@router.post("", response_model=SubUserProfileSyncDto, status_code=201)
@router.post("/", response_model=SubUserProfileSyncDto, status_code=201)
async def create_farmer(
    request: Request,
    body: CreateFarmerApiRequest,
) -> SubUserProfileSyncDto:
    """
    Create a new Member (Farmer) record.
    Security & Business Rules:
    - Strictly restricted: Only authenticated VLCC users can create members.
    - Role constraint: Entity role is locked to Role.FARMER.
    - Center scoping: vlcc_id is strictly overridden to caller's VLCC center.
    - Low boilerplate: Uses get_full_detail_by_code for instant response generation.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    effective_vlcc_id = body.vlcc_id or user.own_id

    farmer_code = body.farmer_code.strip()
    name = body.name.strip()
    email = (
        body.email.strip().lower()
        if body.email and body.email.strip()
        else f"farmer_{farmer_code}_{uuid4().hex[:6]}@dairy.local"
    )
    password = body.password or "Vitco@123"
    mobile = body.mobile.strip() if body.mobile else None

    rank_input = getattr(body, "assigned_chart_rank", None)
    if rank_input is None:
        rank_input = getattr(body, "assigned_rate_chart_id", None)
    try:
        assigned_chart_rank = int(rank_input) if rank_input is not None else 1
    except (ValueError, TypeError):
        assigned_chart_rank = 1

    try:
        milk_type_val = MilkType(int(body.milk_type))
    except Exception:
        milk_type_val = MilkType.MIXED

    has_address = any([body.line, body.city, body.state, body.pincode])
    has_bank = any([body.bank_name, body.account_holder, body.account_number, body.ifsc_code, body.upi_id])

    command = CreateFarmerDetailCommand(
        user=CreateUserCommand(
            name=name,
            email=email,
            mobile=mobile,
            password_hash=password,
            role=Role.FARMER,
            is_active=body.is_active,
            created_by=user.id,
            profile_image=body.profile_image,
        ),
        farmer=CreateFarmerCommand(
            user_id=None,
            farmer_code=farmer_code,
            vlcc_id=effective_vlcc_id,
            assigned_chart_rank=assigned_chart_rank,
            milk_type=milk_type_val,
            profile_image=body.profile_image,
            sms_enabled=body.sms_enabled,
            is_active=body.is_active,
            created_by=user.id,
        ),
        address=CreateAddressCommand(
            line=body.line,
            pincode=body.pincode,
            city=body.city,
            state=body.state,
        ) if has_address else None,
        bank_account=CreateBankAccountCommand(
            bank_name=body.bank_name,
            account_holder=body.account_holder,
            account_number=body.account_number,
            ifsc_code=body.ifsc_code,
            upi_id=body.upi_id,
        ) if has_bank else None,
    )

    handler = GetHandler.farmer_handler(request)
    try:
        await handler.full_create(command, owner=user)
    except FarmerCodeAlreadyExistsException:
        raise HTTPException(status_code=400, detail="Farmer code already exists in this VLCC")
    except Exception as e:
        err_msg = str(e)
        if "UNIQUE constraint failed" in err_msg or "duplicate key" in err_msg:
            raise HTTPException(status_code=400, detail="Farmer code already exists in this VLCC")
        raise HTTPException(status_code=400, detail=f"Failed to create member: {e}")

    # Instant retrieval using get_full_detail_by_code and convert to SubUserProfileSyncDto
    detail = await handler.get_full_detail_by_code(farmer_code, effective_vlcc_id, owner=user)
    if not detail:
        raise HTTPException(status_code=500, detail="Member created but could not be retrieved")

    return farmer_full_detail_to_sub_user_sync_dto(detail)


@router.put("/{farmer_id}", response_model=SubUserProfileSyncDto)
@router.put("/{farmer_id}/", response_model=SubUserProfileSyncDto)
async def update_farmer(
    request: Request,
    farmer_id: UUID,
    body: UpdateFarmerApiRequest,
) -> SubUserProfileSyncDto:
    """
    Update an existing Member (Farmer) record and related User/Address/Bank Profile.
    Security & Business Rules:
    - Strictly restricted: Only authenticated VLCC users can update members.
    - Center scoping: Can only update members belonging to the caller's VLCC center.
    - Entity Guard: Only Farmer role records can be modified; role escalation is blocked.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    vlcc = await _resolve_vlcc(session, user)
    if not vlcc.farmer_enabled:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Farmer modification permission is disabled for this VLCC center.",
        )
    effective_vlcc_id = vlcc.id

    handler = GetHandler.farmer_handler(request)

    # 1. Fetch full existing member detail in one query
    detail = await handler.get_full_detail(farmer_id, owner=user)
    if not detail:
        raise HTTPException(status_code=404, detail="Member not found")

    if detail.farmer.vlcc_id != effective_vlcc_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You can only update members belonging to your own VLCC center.",
        )

    if not detail.farmer.can_modify:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have permission to modify this member.",
        )

    if detail.user.role != Role.FARMER:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only farmer members can be modified via this endpoint.",
        )

    farmer_code = body.farmer_code.strip() if body.farmer_code else detail.farmer.farmer_code
    rank_input = getattr(body, "assigned_chart_rank", None)
    if rank_input is None:
        rank_input = getattr(body, "assigned_rate_chart_id", None)
    if rank_input is not None:
        try:
            assigned_chart_rank = int(rank_input)
        except (ValueError, TypeError):
            assigned_chart_rank = 1
    else:
        assigned_chart_rank = (
            detail.farmer.assigned_chart_rank
            if detail.farmer.assigned_chart_rank is not None
            else 1
        )

    milk_type_val = detail.farmer.milk_type
    if body.milk_type is not None:
        try:
            milk_type_val = MilkType(int(body.milk_type))
        except Exception:
            pass

    sms_enabled = body.sms_enabled if body.sms_enabled is not None else detail.farmer.sms_enabled
    is_active = body.is_active if body.is_active is not None else detail.farmer.is_active

    has_address = any([body.line, body.city, body.state, body.pincode]) or detail.address is not None
    has_bank = (
        any([body.bank_name, body.account_holder, body.account_number, body.ifsc_code, body.upi_id])
        or detail.bank_account is not None
    )

    command = UpdateFarmerDetailCommand(
        farmer=UpdateFarmerCommand(
            id=farmer_id,
            farmer_code=farmer_code,
            vlcc_id=effective_vlcc_id,
            assigned_chart_rank=assigned_chart_rank,
            milk_type=milk_type_val,
            profile_image=body.profile_image or detail.farmer.profile_image,
            sms_enabled=sms_enabled,
            is_active=is_active,
            updated_by=user.id,
        ),
        user=UserData(
            name=body.name.strip() if body.name else detail.user.name,
            email=body.email.strip().lower() if body.email else detail.user.email,
            mobile=body.mobile.strip() if body.mobile else detail.user.mobile,
            role=Role.FARMER,
            is_active=is_active,
            password_hash=body.password if body.password else None,
            profile_image=body.profile_image or detail.user.profile_image,
        ),
        address=AddressData(
            line=body.line if body.line is not None else (detail.address.line if detail.address else None),
            pincode=body.pincode if body.pincode is not None else (detail.address.pincode if detail.address else None),
            city=body.city if body.city is not None else (detail.address.city if detail.address else None),
            state=body.state if body.state is not None else (detail.address.state if detail.address else None),
        ) if has_address else None,
        bank_account=BankAccountData(
            bank_name=body.bank_name if body.bank_name is not None else (detail.bank_account.bank_name if detail.bank_account else None),
            account_holder=body.account_holder if body.account_holder is not None else (detail.bank_account.account_holder if detail.bank_account else None),
            account_number=body.account_number if body.account_number is not None else (detail.bank_account.account_number if detail.bank_account else None),
            ifsc_code=body.ifsc_code if body.ifsc_code is not None else (detail.bank_account.ifsc_code if detail.bank_account else None),
            upi_id=body.upi_id if body.upi_id is not None else (detail.bank_account.upi_id if detail.bank_account else None),
        ) if has_bank else None,
        owner=user,
    )

    try:
        await handler.full_update(command, owner=user)
    except Exception as e:
        err_msg = str(e)
        if "UNIQUE constraint failed" in err_msg or "duplicate key" in err_msg:
            raise HTTPException(status_code=400, detail="Farmer code already exists in this VLCC")
        raise HTTPException(status_code=400, detail=f"Failed to update member: {str(e)}")

    # Fetch updated details in one joined query and convert to SubUserProfileSyncDto
    updated_detail = await handler.get_full_detail(farmer_id, owner=user)
    if not updated_detail:
        raise HTTPException(status_code=500, detail="Member updated but could not be retrieved")

    return farmer_full_detail_to_sub_user_sync_dto(updated_detail)


@router.delete("/{farmer_id}", response_model=DeleteFarmerResponse)
@router.delete("/{farmer_id}/", response_model=DeleteFarmerResponse)
async def delete_farmer(
    request: Request,
    farmer_id: UUID,
):
    """
    Soft delete a Member (Farmer) record.
    Security & Business Rules:
    - Strictly restricted: Only authenticated VLCC users can delete members.
    - Center scoping: Can only delete members belonging to the caller's VLCC center.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session
    vlcc = await _resolve_vlcc(session, user)
    if not vlcc.farmer_enabled:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Farmer modification permission is disabled for this VLCC center.",
        )
    effective_vlcc_id = vlcc.id

    handler = GetHandler.farmer_handler(request)
    detail = await handler.get_full_detail(farmer_id, owner=user)
    if not detail:
        raise HTTPException(status_code=404, detail="Member not found")

    if detail.farmer.vlcc_id != effective_vlcc_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You can only delete members belonging to your own VLCC center.",
        )

    if not detail.farmer.can_modify:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not have permission to delete this member.",
        )

    try:
        await handler.delete(DeleteFarmerCommand(id=farmer_id, deleted_by=user.id, owner=user))
        return DeleteFarmerResponse(
            status=True,
            code=200,
            message="Member deleted successfully",
            farmer_id=farmer_id,
            member_id=farmer_id,
        )
    except FarmerNotFoundException:
        raise HTTPException(status_code=404, detail="Member not found")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete member: {str(e)}")
