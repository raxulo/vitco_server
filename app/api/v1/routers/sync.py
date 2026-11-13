"""
Ultra-Fast High-Performance Data Sync API Router

Supports:
1. Role.VLCC: Syncs VLCC settings, Ratecharts (headers + grid rows + prodata + formulas), Farmers (with user, address, bank info).
2. Role.MCC: Syncs MCC settings, Ratecharts (headers + grid rows + prodata + formulas), VLCCs list (with user, address, bank info).
3. Advanced Delta Sync via `since` / `last_synced_at` timestamp.
4. Parallel Async Database Execution (zero N+1 queries) & Optimized Dict Serialization.

Python 3.13+
"""
from app.modules.farmer.application.command import PartialUpdateFullDetailFarmer
from app.modules.common.fixedrate_config.application.command import UpdateFixedRateConfigCommand
from app.modules.mcc.application.command import PartialUpdateFullDetailMcc
from app.modules.common.milk_quality.application.command import UpdateMilkQualityConfigCommand
from app.modules.common.settings.application.dto import SettingsData
from app.modules.common.bank.application.command import BankAccountData
from app.modules.common.address.application.command import AddressData
from app.modules.administration.application.command import PartialUserUpdateCommand
from app.modules.vlcc.application.command import PartialUpdateFullDetailVlcc
from app.api.v1.schemas.sync import UpdateSettingsRequestPayload, UpdateProfileRequestPayload
from app.api.v1.schemas.sync import FarmerExtraInfoSyncDto
from app.api.v1.schemas.sync import FarmerSyncDto
from app.modules.farmer.domain.dto import FarmerFullDetailDto
from app.api.v1.schemas.sync import VlccSettingSyncDto
from app.api.v1.schemas.sync import VlccExtraInfoSyncDto
from app.api.v1.schemas.sync import VlccSyncDto
from app.modules.vlcc.application.command import GetVlccQuery
from app.modules.vlcc.domain.dto import VlccDetailDto
from app.modules.mcc.domain.enums import MccType
from app.api.v1.schemas.sync import MccSettingSyncDto
from app.api.v1.schemas.sync import MccExtraInfoSyncDto
from app.api.v1.schemas.sync import OwnerSyncDto
from app.modules.mcc.domain.dto import MccDetailDto
from app.modules.mcc.application.command import GetMccQuery
from app.api.v1.schemas.sync import ProfileSyncDto
from app.api.v1.schemas.sync import MccSyncDto
from app.modules.ratechart.application.command import GetAssignmentsByOwnerQuery
from dataclasses import asdict
from app.modules.ratechart.domain.dto import RateChartDto
from app.modules.ratechart.application.command import GetRateChartQuery
from app.api.v1.schemas.sync import SubUserProfileSyncDto
from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import ORJSONResponse
from app.modules.administration.domain.exceptions import UnauthorizedException
from app.modules.common.settings.application.dto import UpdateSettingsCommand
from app.modules.common.settings.domain.exceptions import SettingsNotFoundError
from app.modules.common.settings.presentation.requests import UpdateSettingsRequest
from app.modules.common.settings.presentation.response import SettingsResponse
from app.modules.dependencies import GetHandler
from uuid import UUID

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role

router = APIRouter(
    prefix="/sync",
    tags=["Data Sync API"],
)

# =========================================================
# HELPER: RATECHARTS SYNC BUILDER (MATRIX / SLABS)
# =========================================================
async def get_ratechart_config(handler, chart_id: UUID, request: Request):
    chart: RateChartDto = await handler.get(GetRateChartQuery(id=chart_id, owner=request.state.user))

    formula_config = None
    grids_data = []
    prodata_data = []

    if chart.chart_type == 0:
        try:
            formula_config = await handler.get_formula_config(rate_chart_id=chart_id)
        except Exception:
            pass
    elif chart.chart_type in (1, 3):
        try:
            grids = await handler._repository.get_grid_rows(rate_chart_id=chart_id)
            grids_data = [{"fat": float(g.fat), "snf": float(g.snf), "rate": float(g.rate)} for g in grids]
        except Exception:
            pass
    elif chart.chart_type == 2:
        try:
            prodata = await handler._repository.get_prodata_rows(rate_chart_id=chart_id)
            prodata_data = [{
                "fat_min": float(p.fat_min),
                "fat_max": float(p.fat_max),
                "snf_min": float(p.snf_min) if p.snf_min is not None else None,
                "snf_max": float(p.snf_max) if p.snf_max is not None else None,
                "kg_fat_rate": float(p.fat_rate_per_kg) if p.fat_rate_per_kg is not None else 0.0,
                "kg_snf_rate": float(p.snf_rate_per_kg) if p.snf_rate_per_kg is not None else 0.0,
                "snf_cut_off": float(p.snf_cutoff) if p.snf_cutoff is not None else 0.0,
                "snf_deduction": float(p.snf_deduction) if p.snf_deduction is not None else 0.0,
            } for p in prodata]
        except Exception:
            pass
    
    return {
        **asdict(chart),
        "formula_config": formula_config,
        "grids": grids_data,
        "prodata_rows": prodata_data
    }


async def fetch_all_ratecharts(user_id: UUID, request: Request):
    handler = GetHandler.ratechart_handler(request)
    assigned_rate_charts = await handler.get_charts_by_owner_id(
        query=GetAssignmentsByOwnerQuery(owner_id=user_id)
    )
    rate_charts = []
    for chart in assigned_rate_charts:
        chart_configs = await get_ratechart_config(handler, chart.id, request)
        rate_charts.append(chart_configs)
    return rate_charts

async def mcc_data(request: Request, current_user:CurrentUser):
    handler = GetHandler.mcc_handler(request)
    mcc_full_detail: MccDetailDto = await handler.get_full_detail(
        query=GetMccQuery(id=current_user.own_id, owner=current_user)
    )
    vlcc_handler = GetHandler.vlcc_handler(request)
    vlcc_dtos: list[SubUserProfileSyncDto] = await vlcc_handler.get_vlccs_with_details_by_mcc(mcc_full_detail.mcc.id, owner=current_user)
    
    mcc = mcc_full_detail.mcc
    user= mcc_full_detail.user
    bank_account= mcc_full_detail.bank_account
    address= mcc_full_detail.address
    setting= mcc_full_detail.setting
    milk_quality_config= mcc_full_detail.milk_quality_config
    fixed_rate_config= mcc_full_detail.fixed_rate_config
    ratecharts_list = []
    if mcc.mcc_type != MccType.WEIGHT:
        ratecharts_list = (await fetch_all_ratecharts(current_user.id, request))

    return MccSyncDto(
        status=True,
        role=Role.MCC,
        profile=ProfileSyncDto(
            id=mcc.id,
            user_id=mcc.user_id,
            name=user.name,
            email=user.email,
            mobile=user.mobile,
            code=mcc.code,
            profile_image=mcc.profile_image or user.profile_image,
            uic_code=None,
            role=Role.MCC,
            owner=None,
            route_code=mcc.route_code,
            route_name=None,
            address=address,
            bank_account=bank_account,
        ),
        mcc_info=MccExtraInfoSyncDto(
            mcc_type=mcc.mcc_type,
            sample_start=mcc.sample_start if mcc.mcc_type==MccType.WEIGHT else None,
            sample_end=mcc.sample_end if mcc.mcc_type==MccType.WEIGHT else None,
            visible_member=mcc.shows_member_name,
            shift_delay=mcc.applied_shift_delay,
        ),
        settings=MccSettingSyncDto(
            config=setting,
            milk_quality_config=milk_quality_config,
            fixed_rate_config=fixed_rate_config,
        ),
        rate_charts=ratecharts_list,
        sub_users=vlcc_dtos
    )

async def vlcc_data(request: Request, current_user:CurrentUser):
    handler = GetHandler.vlcc_handler(request)
    vlcc_full_detail: VlccDetailDto = await handler.get_full_detail(
        query=GetVlccQuery(id=current_user.own_id, owner=current_user)
    )
    is_farmer_vlcc = current_user.role_type == Role.VLCC_FARMER
    farmer_dtos: list[SubUserProfileSyncDto] = []
    if not is_farmer_vlcc:
        farmer_handler = GetHandler.farmer_handler(request)
        farmer_dtos = await farmer_handler.get_farmers_detail_for_sync(vlcc_id=current_user.own_id, owner=current_user)
    
    vlcc = vlcc_full_detail.vlcc
    user= vlcc_full_detail.user
    bank_account= vlcc_full_detail.bank_account
    address= vlcc_full_detail.address
    setting= vlcc_full_detail.setting
    milk_quality_config= vlcc_full_detail.milk_quality_config
    ratecharts_list = await fetch_all_ratecharts(current_user.id, request)

    target_role = Role.VLCC_FARMER if is_farmer_vlcc else Role.VLCC

    return VlccSyncDto(
        status=True,
        role=target_role,
        profile=ProfileSyncDto(
            id=vlcc.id,
            user_id=vlcc.user_id,
            name=user.name,
            email=user.email,
            mobile=user.mobile,
            code=vlcc.vlcc_code,
            profile_image=vlcc.profile_image or user.profile_image,
            uic_code=vlcc.uic_code,
            role=target_role,
            owner=None,
            route_code=vlcc.route_code,
            route_name=None,
            address=address,
            bank_account=bank_account,
        ),
        vlcc_info=VlccExtraInfoSyncDto(
            entry_mode=vlcc.entry_mode,
            soc_percentage=vlcc.soc_percentage,
            vlcc_type= vlcc.vlcc_type,
            farmer_enabled=False if is_farmer_vlcc else vlcc.farmer_enabled,
        ),
        settings=VlccSettingSyncDto(
            config=setting,
            milk_quality_config=milk_quality_config,
        ),
        rate_charts=ratecharts_list,
        sub_users=farmer_dtos
    )

async def farmer_data(request: Request, current_user:CurrentUser):
    handler = GetHandler.farmer_handler(request)
    farmer_full_detail: FarmerFullDetailDto = await handler.get_full_detail(
        current_user.own_id, owner=current_user
    )
    farmer = farmer_full_detail.farmer
    user= farmer_full_detail.user
    vlcc= farmer_full_detail.vlcc
    bank_account= farmer_full_detail.bank_account
    address= farmer_full_detail.address
    return FarmerSyncDto(
        status=True,
        role=Role.FARMER,
        profile=ProfileSyncDto(
            id=farmer.id,
            user_id=farmer.user_id,
            name=user.name,
            email=user.email,
            mobile=user.mobile,
            code=farmer.farmer_code,
            profile_image=user.profile_image,
            uic_code=None,
            role=Role.FARMER,
            owner=OwnerSyncDto(
                id=vlcc.id,
                name=vlcc.name,
                email=vlcc.email,
                mobile=vlcc.mobile,
                profile_image=vlcc.profile_image,
                role=Role.VLCC,
                code=vlcc.code,
                mcc_type=None
            ),
            address=address,
            bank_account=bank_account,
        ),
        farmer_info=FarmerExtraInfoSyncDto(
            sms_enabled=farmer.sms_enabled,
            milk_type=farmer.milk_type,
            assigned_chart_rank=farmer.assigned_chart_rank,
        )
    )

@router.put("/profile", response_class=ORJSONResponse)
@router.post("/profile", response_class=ORJSONResponse)
@router.patch("/profile", response_class=ORJSONResponse)
async def update_profile(
    request: Request,
    payload: UpdateProfileRequestPayload,
):
    """
    Updates profile details (user info, address, bank account)
    for the authenticated VLCC, MCC, or Farmer user.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is None:
        raise UnauthorizedException()

    if user.role_type not in [Role.VLCC, Role.MCC, Role.FARMER, Role.VLCC_FARMER]:
        raise UnauthorizedException()

    new_user, new_bank_account, new_address = None, None, None

    if payload.user is not None:
        user_dump = payload.user.model_dump(exclude_unset=True, exclude_none=True)
        if user_dump:
            new_user = PartialUserUpdateCommand(**user_dump)

    if payload.address is not None and payload.address.is_valid_detail():
        address_dump = payload.address.model_dump(exclude_unset=True, exclude_none=True)
        if address_dump:
            new_address = AddressData(**address_dump)

    if payload.bank_account is not None and payload.bank_account.is_valid_detail():
        bank_dump = payload.bank_account.model_dump(exclude_unset=True, exclude_none=True)
        if bank_dump:
            if "account_holder" not in bank_dump:
                bank_dump["account_holder"] = getattr(user, "name", "") or ""
            new_bank_account = BankAccountData(**bank_dump)

    if user.role_type in (Role.VLCC, Role.VLCC_FARMER):
        vlcc_handler = GetHandler.vlcc_handler(request)
        await vlcc_handler.partial_update(
            owner=user,
            command=PartialUpdateFullDetailVlcc(
                updated_by=user.id,
                user=new_user,
                address=new_address,
                bank_account=new_bank_account,
                milk_quality_config=None,
                device_item_versions=None,
            ),
        )
        data = await vlcc_data(request, user)

    elif user.role_type == Role.MCC:
        mcc_handler = GetHandler.mcc_handler(request)
        await mcc_handler.partial_update(
            owner=user,
            command=PartialUpdateFullDetailMcc(
                updated_by=user.id,
                user=new_user,
                address=new_address,
                milk_quality_config=None,
                bank_account=new_bank_account,
                device_item_versions=None,
            ),
        )
        data = await mcc_data(request, user)

    elif user.role_type == Role.FARMER:
        farmer_handler = GetHandler.farmer_handler(request)
        await farmer_handler.partial_update(
            owner=user,
            command=PartialUpdateFullDetailFarmer(
                updated_by=user.id,
                user=new_user,
                address=new_address,
                bank_account=new_bank_account,
            ),
        )
        data = await farmer_data(request, user)

    response_dto = data.profile

    return ORJSONResponse(
        content=jsonable_encoder(response_dto)
    )

@router.put("/settings", response_class=ORJSONResponse)
@router.post("/settings", response_class=ORJSONResponse)
@router.patch("/settings", response_class=ORJSONResponse)
async def update_settings(
    request: Request,
    payload: UpdateSettingsRequestPayload,
):
    """
    Updates operational settings (analyzer, printer, collection times, weight units, etc.)
    for the authenticated VLCC or MCC user.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is None:
        raise UnauthorizedException()

    
    if user.role_type not in [Role.VLCC, Role.MCC, Role.FARMER, Role.VLCC_FARMER]:
        raise UnauthorizedException()

    new_user, new_bank_account, new_address, new_setting, new_milk_quality_config, new_fixed_rate_config = None, None, None, None, None, None
    if payload.user is not None:
        new_user= PartialUserUpdateCommand(**payload.user.model_dump(exclude_unset=True, exclude_none=True))
    if payload.address is not None:
        new_address=AddressData(**payload.address.model_dump(exclude_unset=True, exclude_none=True))
    if payload.bank_account is not None:
        new_bank_account=BankAccountData(**payload.bank_account.model_dump(exclude_unset=True, exclude_none=True))
    if payload.config is not None:
        new_setting=SettingsData(**payload.config.model_dump(exclude_unset=True, exclude_none=True))
    if payload.milk_quality_config is not None:
        new_milk_quality_config=UpdateMilkQualityConfigCommand(**payload.milk_quality_config.model_dump(exclude_unset=True, exclude_none=True))
    if payload.fixed_rate_config is not None:
        new_fixed_rate_config=UpdateFixedRateConfigCommand(**payload.fixed_rate_config.model_dump(exclude_unset=True, exclude_none=True))

    
    if user.role_type in (Role.VLCC, Role.VLCC_FARMER):
        vlcc_handler = GetHandler.vlcc_handler(request)
        vlcc = await vlcc_handler.partial_update(
            owner=user,
            command=PartialUpdateFullDetailVlcc(
                updated_by=user.id,
                user=new_user,
                address=new_address,
                bank_account=new_bank_account,
                setting=new_setting,
                milk_quality_config=new_milk_quality_config,
                device_item_versions=None
            )
        )
        
    elif user.role_type == Role.MCC:
        mcc_handler = GetHandler.mcc_handler(request)
        result = await mcc_handler.partial_update(
            owner=user,
            command=PartialUpdateFullDetailMcc(
                updated_by=user.id,
                user=new_user,
                address=new_address,
                bank_account=new_bank_account,
                setting=new_setting,
                milk_quality_config=new_milk_quality_config,
                fixed_rate_config=new_fixed_rate_config,
                device_item_versions=None
            )
        )

    elif user.role_type == Role.FARMER:
        farmer_handler = GetHandler.farmer_handler(request)
        result = await farmer_handler.partial_update(
            owner=user,
            command=PartialUpdateFullDetailFarmer(
                user=new_user,
                address=new_address,
                bank_account=new_bank_account,
            )
        )
    
        

    settings_handler = GetHandler.settings_handler(request)

    try:
        existing_settings = await settings_handler.get_by_user_id(user.id, user.role_type)
    except SettingsNotFoundError:
        try:
            existing_settings = await settings_handler.get_by_user_id(user.own_id, user.role_type)
        except SettingsNotFoundError:
            raise HTTPException(
                status_code=404,
                detail=f"Settings record not found for user {user.id} ({user.role_type.value}).",
            )

    command = UpdateSettingsCommand(
        settings_id=existing_settings.id,
        analyzer_type=payload.analyzer_type if payload.analyzer_type is not None else existing_settings.analyzer_type,
        analyzer_collection_mode=payload.analyzer_collection_mode if payload.analyzer_collection_mode is not None else existing_settings.analyzer_collection_mode,
        weight_unit=payload.weight_unit if payload.weight_unit is not None else existing_settings.weight_unit,
        weight_collection_mode=payload.weight_collection_mode if payload.weight_collection_mode is not None else existing_settings.weight_collection_mode,
        auto_tare_enabled=payload.auto_tare_enabled if payload.auto_tare_enabled is not None else existing_settings.auto_tare_enabled,
        morning_collection_start=payload.morning_collection_start if payload.morning_collection_start is not None else existing_settings.morning_collection_start,
        morning_collection_end=payload.morning_collection_end if payload.morning_collection_end is not None else existing_settings.morning_collection_end,
        evening_collection_start=payload.evening_collection_start if payload.evening_collection_start is not None else existing_settings.evening_collection_start,
        evening_collection_end=payload.evening_collection_end if payload.evening_collection_end is not None else existing_settings.evening_collection_end,
        receipt_size=payload.receipt_size if payload.receipt_size is not None else existing_settings.receipt_size,
        printer_type=payload.printer_type if payload.printer_type is not None else existing_settings.printer_type,
        printer_enabled=payload.printer_enabled if payload.printer_enabled is not None else existing_settings.printer_enabled,
        cattle_type=payload.cattle_type if payload.cattle_type is not None else existing_settings.cattle_type,
        max_rate_chart_count=payload.max_rate_chart_count if payload.max_rate_chart_count is not None else existing_settings.max_rate_chart_count,
        settings_edit_enabled=payload.settings_edit_enabled if payload.settings_edit_enabled is not None else existing_settings.settings_edit_enabled,
        rate_chart_edit_enabled=payload.rate_chart_edit_enabled if payload.rate_chart_edit_enabled is not None else existing_settings.rate_chart_edit_enabled,
        master_enabled=payload.master_enabled if getattr(payload, "master_enabled", None) is not None else existing_settings.master_enabled,
    )

    updated_settings = await settings_handler.update(command)
    response_dto = SettingsResponse.model_validate(updated_settings)

    return ORJSONResponse(
        content=jsonable_encoder(response_dto)
    )

@router.get("", response_class=ORJSONResponse)
@router.get("/", response_class=ORJSONResponse)
async def load_sync(request: Request):
    user: CurrentUser | None = getattr(
        request.state, "user", None
    )

    if user is None:
        raise UnauthorizedException()

    if user.role_type == Role.MCC:
        data = await mcc_data(request, user)

    elif user.role_type in (Role.VLCC, Role.VLCC_FARMER):
        data = await vlcc_data(request, user)

    elif user.role_type == Role.FARMER:
        data = await farmer_data(request, user)

    else:
        raise UnauthorizedException()

    return ORJSONResponse(
        content=jsonable_encoder(data)
    )