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
# def parse_since(since: str | None) -> datetime | None:
#     """Parses optional timestamp integer/float or ISO 8601 string into UTC datetime."""
#     if not since or not str(since).strip():
#         return None
#     val = str(since).strip()
#     try:
#         ts = float(val)
#         return datetime.fromtimestamp(ts, tz=timezone.utc)
#     except ValueError:
#         pass
#     try:
#         dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
#         if dt.tzinfo is None:
#             dt = dt.replace(tzinfo=timezone.utc)
#         return dt
#     except ValueError:
#         return None


# # =========================================================
# # HELPER: VLCC SYNC DATA BUILDER
# # =========================================================

# async def fetch_vlcc_data(session, user_id: UUID) -> tuple[dict[str, Any] | None, UUID | None, int]:
#     """Fetches VLCC master record, user profile, settings and quality configs in a single join."""
#     stmt = (
#         select(
#             VlccModel,
#             UserModel,
#             SettingsModel,
#             MilkQualityConfigModel
#         )
#         .join(UserModel, UserModel.id == VlccModel.user_id)
#         .outerjoin(SettingsModel, SettingsModel.id == VlccModel.settings_id)
#         .outerjoin(MilkQualityConfigModel, MilkQualityConfigModel.id == VlccModel.milk_quality_config_id)
#         .where(VlccModel.user_id == user_id)
#     )
#     res = await session.execute(stmt)
#     row = res.first()

#     if not row:
#         # Fallback: check if user created a VLCC record
#         stmt_alt = (
#             select(
#                 VlccModel,
#                 UserModel,
#                 SettingsModel,
#                 MilkQualityConfigModel
#             )
#             .join(UserModel, UserModel.id == VlccModel.user_id)
#             .outerjoin(SettingsModel, SettingsModel.id == VlccModel.settings_id)
#             .outerjoin(MilkQualityConfigModel, MilkQualityConfigModel.id == VlccModel.milk_quality_config_id)
#             .where(VlccModel.created_by == user_id)
#         )
#         res_alt = await session.execute(stmt_alt)
#         row = res_alt.first()

#     if not row:
#         return None, None, 1

#     vlcc, user, settings, quality = row
#     assigned_rank = int(vlcc.assigned_chart_rank or 1)

#     vlcc_payload = {
#         "id": str(vlcc.id),
#         "user_id": str(vlcc.user_id),
#         "vlcc_code": vlcc.vlcc_code,
#         "uic_code": vlcc.uic_code,
#         "name": vlcc.name,
#         "contact_person": vlcc.contact_person,
#         "entry_mode": vlcc.entry_mode.value if hasattr(vlcc.entry_mode, 'value') else str(vlcc.entry_mode),
#         "soc_percentage": float(vlcc.soc_percentage) if vlcc.soc_percentage is not None else 0.0,
#         "farmer_enabled": bool(vlcc.farmer_enabled),
#         "assigned_chart_rank": assigned_rank,
#         "route_code": vlcc.route_code,
#         "is_active": bool(vlcc.is_active),
#         "user_profile": {
#             "name": user.name if user else "",
#             "email": user.email if user else "",
#             "mobile": user.mobile if user else "",
#             "profile_url": user.profile_url if user else None,
#         },
#         "settings": {
#             "id": str(settings.id) if settings else None,
#             "analyzer_type": settings.analyzer_type.value if settings and hasattr(settings.analyzer_type, 'value') else None,
#             "analyzer_collection_mode": settings.analyzer_collection_mode.value if settings and hasattr(settings.analyzer_collection_mode, 'value') else None,
#             "weight_unit": settings.weight_unit.value if settings and hasattr(settings.weight_unit, 'value') else None,
#             "weight_collection_mode": settings.weight_collection_mode.value if settings and hasattr(settings.weight_collection_mode, 'value') else None,
#             "auto_tare_enabled": settings.auto_tare_enabled if settings else False,
#             "morning_collection_start": settings.morning_collection_start if settings else "06:00",
#             "morning_collection_end": settings.morning_collection_end if settings else "10:00",
#             "evening_collection_start": settings.evening_collection_start if settings else "12:00",
#             "evening_collection_end": settings.evening_collection_end if settings else "22:00",
#             "receipt_size": settings.receipt_size.value if settings and hasattr(settings.receipt_size, 'value') else None,
#             "printer_type": settings.printer_type.value if settings and hasattr(settings.printer_type, 'value') else None,
#             "printer_enabled": settings.printer_enabled if settings else False,
#             "cattle_type": settings.cattle_type.value if settings and hasattr(settings.cattle_type, 'value') else None,
#             "max_rate_chart_count": settings.max_rate_chart_count if settings else 5,
#             "settings_edit_enabled": settings.settings_edit_enabled if settings else False,
#             "rate_chart_edit_enabled": settings.rate_chart_edit_enabled if settings else False,
#         } if settings else None,
#         "milk_quality_config": {
#             "id": str(quality.id) if quality else None,
#             "cow_min_fat": quality.cow_min_fat if quality else 0.0,
#             "cow_max_fat": quality.cow_max_fat if quality else 0.0,
#             "cow_min_snf": quality.cow_min_snf if quality else 0.0,
#             "cow_max_snf": quality.cow_max_snf if quality else 0.0,
#             "buffalo_min_fat": quality.buffalo_min_fat if quality else 0.0,
#             "buffalo_max_fat": quality.buffalo_max_fat if quality else 0.0,
#             "buffalo_min_snf": quality.buffalo_min_snf if quality else 0.0,
#             "buffalo_max_snf": quality.buffalo_max_snf if quality else 0.0,
#         } if quality else None,
#     }

#     return vlcc_payload, vlcc.id, assigned_rank


# async def fetch_farmers_for_vlcc(
#     session,
#     vlcc_id: UUID | None,
#     user_id: UUID,
#     since_dt: datetime | None = None
# ) -> list[dict[str, Any]]:
#     """Ultra-fast batch query fetching all farmers + user + address + bank info for a VLCC."""
#     stmt = (
#         select(
#             FarmerModel,
#             UserModel.name.label("farmer_name"),
#             UserModel.email.label("farmer_email"),
#             UserModel.mobile.label("farmer_mobile"),
#             UserModel.profile_url.label("farmer_profile_url"),
#             UserModel.is_active.label("user_is_active"),
#             AddressModel,
#             BankAccountModel
#         )
#         .join(UserModel, UserModel.id == FarmerModel.user_id)
#         .outerjoin(AddressModel, AddressModel.id == FarmerModel.address_id)
#         .outerjoin(BankAccountModel, BankAccountModel.id == FarmerModel.bank_account_id)
#     )

#     if vlcc_id is not None:
#         stmt = stmt.where(or_(FarmerModel.vlcc_id == vlcc_id, FarmerModel.created_by == user_id))
#     else:
#         stmt = stmt.where(FarmerModel.created_by == user_id)

#     if since_dt is not None:
#         stmt = stmt.where(
#             or_(
#                 FarmerModel.updated_at >= since_dt,
#                 UserModel.updated_at >= since_dt
#             )
#         )

#     stmt = stmt.order_by(FarmerModel.farmer_code.asc())
#     res = await session.execute(stmt)
#     rows = res.all()

#     farmers_list = []
#     for row in rows:
#         farmer = row.FarmerModel
#         farmer_name = row.farmer_name or ""
#         farmer_email = row.farmer_email or ""
#         farmer_mobile = row.farmer_mobile or ""
#         farmer_profile_url = row.farmer_profile_url or None
#         user_is_active = row.user_is_active if row.user_is_active is not None else True
#         address = row.AddressModel
#         bank = row.BankAccountModel

#         farmers_list.append({
#             "id": str(farmer.id),
#             "user_id": str(farmer.user_id),
#             "farmer_code": farmer.farmer_code,
#             "vlcc_id": str(farmer.vlcc_id) if farmer.vlcc_id else None,
#             "name": farmer_name,
#             "email": farmer_email,
#             "mobile": farmer_mobile,
#             "profile_url": farmer_profile_url,
#             "is_active": bool(user_is_active),
#             "address": {
#                 "id": str(address.id),
#                 "line": address.line,
#                 "city": address.city,
#                 "state": address.state,
#                 "pincode": address.pincode,
#             } if address else None,
#             "bank_account": {
#                 "id": str(bank.id),
#                 "bank_name": bank.bank_name,
#                 "account_holder": bank.account_holder,
#                 "account_number": bank.account_number,
#                 "ifsc_code": bank.ifsc_code,
#                 "upi_id": bank.upi_id,
#             } if bank else None,
#             "updated_at": farmer.updated_at.isoformat() if hasattr(farmer, 'updated_at') and farmer.updated_at else None,
#         })

#     return farmers_list


# # =========================================================
# # HELPER: MCC SYNC DATA BUILDER
# # =========================================================

# async def fetch_mcc_data(session, user_id: UUID) -> tuple[dict[str, Any] | None, UUID | None, int | None]:
#     """Fetches MCC master record, user profile, settings, milk quality config, address, and bank info."""
#     stmt = (
#         select(MccModel, UserModel, SettingsModel, MilkQualityConfigModel, AddressModel, BankAccountModel)
#         .join(UserModel, UserModel.id == MccModel.user_id)
#         .outerjoin(SettingsModel, SettingsModel.id == MccModel.settings_id)
#         .outerjoin(MilkQualityConfigModel, MilkQualityConfigModel.id == MccModel.milk_quality_config_id)
#         .outerjoin(AddressModel, AddressModel.id == MccModel.address_id)
#         .outerjoin(BankAccountModel, BankAccountModel.id == MccModel.bank_account_id)
#         .where(MccModel.user_id == user_id)
#     )
#     res = await session.execute(stmt)
#     row = res.first()

#     if not row:
#         stmt_alt = (
#             select(MccModel, UserModel, SettingsModel, MilkQualityConfigModel, AddressModel, BankAccountModel)
#             .join(UserModel, UserModel.id == MccModel.user_id)
#             .outerjoin(SettingsModel, SettingsModel.id == MccModel.settings_id)
#             .outerjoin(MilkQualityConfigModel, MilkQualityConfigModel.id == MccModel.milk_quality_config_id)
#             .outerjoin(AddressModel, AddressModel.id == MccModel.address_id)
#             .outerjoin(BankAccountModel, BankAccountModel.id == MccModel.bank_account_id)
#             .where(MccModel.created_by == user_id)
#         )
#         res_alt = await session.execute(stmt_alt)
#         row = res_alt.first()

#     if not row:
#         return None, None, None

#     mcc, user, settings, quality, address, bank = row

#     mcc_payload = {
#         "id": str(mcc.id),
#         "user_id": str(mcc.user_id),
#         "code": mcc.code,
#         "name": mcc.name,
#         "mcc_type": mcc.mcc_type.value if hasattr(mcc.mcc_type, 'value') else str(mcc.mcc_type),
#         "route_code": mcc.route_code,
#         "sample_start": mcc.sample_start,
#         "sample_end": getattr(mcc, 'sample_end', None),
#         "is_active": getattr(mcc, 'is_active', True),
#         "user_profile": {
#             "name": user.name if user else "",
#             "email": user.email if user else "",
#             "mobile": user.mobile if user else "",
#             "profile_url": user.profile_url if user else None,
#         },
#         "address": {
#             "id": str(address.id),
#             "line": address.line,
#             "city": address.city,
#             "state": address.state,
#             "pincode": address.pincode,
#         } if address else None,
#         "bank_account": {
#             "id": str(bank.id),
#             "bank_name": bank.bank_name,
#             "account_holder": bank.account_holder,
#             "account_number": bank.account_number,
#             "ifsc_code": bank.ifsc_code,
#             "upi_id": bank.upi_id,
#         } if bank else None,
#         "settings": {
#             "id": str(settings.id) if settings else None,
#             "analyzer_type": settings.analyzer_type.value if settings and hasattr(settings.analyzer_type, 'value') else None,
#             "analyzer_collection_mode": settings.analyzer_collection_mode.value if settings and hasattr(settings.analyzer_collection_mode, 'value') else None,
#             "weight_unit": settings.weight_unit.value if settings and hasattr(settings.weight_unit, 'value') else None,
#             "weight_collection_mode": settings.weight_collection_mode.value if settings and hasattr(settings.weight_collection_mode, 'value') else None,
#             "auto_tare_enabled": settings.auto_tare_enabled if settings else False,
#             "morning_collection_start": settings.morning_collection_start if settings else "06:00",
#             "morning_collection_end": settings.morning_collection_end if settings else "10:00",
#             "evening_collection_start": settings.evening_collection_start if settings else "12:00",
#             "evening_collection_end": settings.evening_collection_end if settings else "22:00",
#             "receipt_size": settings.receipt_size.value if settings and hasattr(settings.receipt_size, 'value') else None,
#             "printer_type": settings.printer_type.value if settings and hasattr(settings.printer_type, 'value') else None,
#             "printer_enabled": settings.printer_enabled if settings else False,
#             "cattle_type": settings.cattle_type.value if settings and hasattr(settings.cattle_type, 'value') else None,
#             "max_rate_chart_count": settings.max_rate_chart_count if settings else 5,
#             "settings_edit_enabled": settings.settings_edit_enabled if settings else False,
#             "rate_chart_edit_enabled": settings.rate_chart_edit_enabled if settings else False,
#         } if settings else None,
#         "milk_quality_config": {
#             "id": str(quality.id) if quality else None,
#             "cow_min_fat": quality.cow_min_fat if quality else 0.0,
#             "cow_max_fat": quality.cow_max_fat if quality else 0.0,
#             "cow_min_snf": quality.cow_min_snf if quality else 0.0,
#             "cow_max_snf": quality.cow_max_snf if quality else 0.0,
#             "buffalo_min_fat": quality.buffalo_min_fat if quality else 0.0,
#             "buffalo_max_fat": quality.buffalo_max_fat if quality else 0.0,
#             "buffalo_min_snf": quality.buffalo_min_snf if quality else 0.0,
#             "buffalo_max_snf": quality.buffalo_max_snf if quality else 0.0,
#         } if quality else None,
#     }

#     return mcc_payload, mcc.id, mcc.route_code


# async def fetch_vlccs_for_mcc(
#     session,
#     mcc_id: UUID | None,
#     user_id: UUID,
#     route_code: int | None = None,
#     since_dt: datetime | None = None
# ) -> list[dict[str, Any]]:
#     """Ultra-fast batch query fetching all VLCCs under MCC + user + address + bank info."""
#     stmt = (
#         select(
#             VlccModel,
#             UserModel.name.label("vlcc_user_name"),
#             UserModel.email.label("vlcc_user_email"),
#             UserModel.mobile.label("vlcc_user_mobile"),
#             UserModel.is_active.label("user_is_active"),
#             AddressModel,
#             BankAccountModel
#         )
#         .join(UserModel, UserModel.id == VlccModel.user_id)
#         .outerjoin(AddressModel, AddressModel.id == VlccModel.address_id)
#         .outerjoin(BankAccountModel, BankAccountModel.id == VlccModel.bank_account_id)
#     )

#     conditions = [VlccModel.created_by == user_id]
#     if route_code is not None:
#         conditions.append(VlccModel.route_code == route_code)

#     stmt = stmt.where(or_(*conditions))

#     if since_dt is not None:
#         stmt = stmt.where(
#             or_(
#                 VlccModel.updated_at >= since_dt,
#                 UserModel.updated_at >= since_dt
#             )
#         )

#     stmt = stmt.order_by(VlccModel.vlcc_code.asc())
#     res = await session.execute(stmt)
#     rows = res.all()

#     if not rows:
#         # Fallback: fetch all active VLCCs if none match explicit created_by filter
#         stmt_fallback = (
#             select(
#                 VlccModel,
#                 UserModel.name.label("vlcc_user_name"),
#                 UserModel.email.label("vlcc_user_email"),
#                 UserModel.mobile.label("vlcc_user_mobile"),
#                 UserModel.is_active.label("user_is_active"),
#                 AddressModel,
#                 BankAccountModel
#             )
#             .join(UserModel, UserModel.id == VlccModel.user_id)
#             .outerjoin(AddressModel, AddressModel.id == VlccModel.address_id)
#             .outerjoin(BankAccountModel, BankAccountModel.id == VlccModel.bank_account_id)
#             .order_by(VlccModel.vlcc_code.asc())
#         )
#         if since_dt is not None:
#             stmt_fallback = stmt_fallback.where(
#                 or_(
#                     VlccModel.updated_at >= since_dt,
#                     UserModel.updated_at >= since_dt
#                 )
#             )
#         res_fb = await session.execute(stmt_fallback)
#         rows = res_fb.all()

#     vlccs_list = []
#     for row in rows:
#         vlcc = row.VlccModel
#         vlcc_user_name = row.vlcc_user_name or ""
#         vlcc_user_email = row.vlcc_user_email or ""
#         vlcc_user_mobile = row.vlcc_user_mobile or ""
#         user_is_active = row.user_is_active if row.user_is_active is not None else True
#         address = row.AddressModel
#         bank = row.BankAccountModel

#         vlccs_list.append({
#             "id": str(vlcc.id),
#             "user_id": str(vlcc.user_id),
#             "code": vlcc.vlcc_code,
#             "vlcc_code": vlcc.vlcc_code,
#             "farmer_code": vlcc.vlcc_code,
#             "uic_code": vlcc.uic_code,
#             "name": vlcc.name,
#             "contact_person": vlcc.contact_person,
#             "mobile": vlcc_user_mobile,
#             "email": vlcc_user_email,
#             "entry_mode": vlcc.entry_mode.value if hasattr(vlcc.entry_mode, 'value') else str(vlcc.entry_mode),
#             "soc_percentage": float(vlcc.soc_percentage) if vlcc.soc_percentage is not None else 0.0,
#             "route_code": vlcc.route_code,
#             "farmer_enabled": bool(vlcc.farmer_enabled),
#             "assigned_chart_rank": int(vlcc.assigned_chart_rank or 1),
#             "is_active": bool(vlcc.is_active and user_is_active),
#             "user_profile": {
#                 "name": vlcc_user_name,
#                 "email": vlcc_user_email,
#                 "mobile": vlcc_user_mobile,
#             },
#             "address": {
#                 "id": str(address.id),
#                 "line": address.line,
#                 "city": address.city,
#                 "state": address.state,
#                 "pincode": address.pincode,
#             } if address else None,
#             "bank_account": {
#                 "id": str(bank.id),
#                 "bank_name": bank.bank_name,
#                 "account_holder": bank.account_holder,
#                 "account_number": bank.account_number,
#                 "ifsc_code": bank.ifsc_code,
#                 "upi_id": bank.upi_id,
#             } if bank else None,
#             "updated_at": vlcc.updated_at.isoformat() if hasattr(vlcc, 'updated_at') and vlcc.updated_at else None,
#         })

#     return vlccs_list


# async def fetch_ratecharts_data(
#     session,
#     owner_id: UUID,
#     owner_role: Role,
#     since_dt: datetime | None = None
# ) -> list[dict[str, Any]]:
#     """Batch query fetching rate charts (assigned + user-created) + grid rows + prodata rows + formulas."""
#     # 1. Find assigned rate chart IDs
#     assign_stmt = (
#         select(RateChartAssignmentModel.rate_chart_id)
#         .where(
#             RateChartAssignmentModel.owner_id == owner_id,
#             RateChartAssignmentModel.is_active.is_(True)
#         )
#     )
#     res_assign = await session.execute(assign_stmt)
#     assigned_ids = set(res_assign.scalars().all())

#     # 2. Find rate charts created by this user
#     created_stmt = (
#         select(RateChartModel.id)
#         .where(RateChartModel.created_by == owner_id)
#     )
#     res_created = await session.execute(created_stmt)
#     created_ids = set(res_created.scalars().all())

#     # Combine assigned and created rate chart IDs
#     chart_ids = assigned_ids.union(created_ids)

#     # 3. Fallback to active system rate charts if user has no assigned or created rate charts
#     if not chart_ids:
#         default_stmt = select(RateChartModel.id).where(RateChartModel.status == RateChartStatus.ACTIVE).limit(20)
#         res_def = await session.execute(default_stmt)
#         chart_ids = set(res_def.scalars().all())

#     if not chart_ids:
#         return []

#     # Fetch RateChart headers
#     chart_stmt = select(RateChartModel).where(RateChartModel.id.in_(chart_ids))
#     if since_dt is not None:
#         chart_stmt = chart_stmt.where(RateChartModel.updated_at >= since_dt)

#     res_charts = await session.execute(chart_stmt)
#     rate_charts = res_charts.scalars().all()

#     if not rate_charts:
#         return []

#     valid_chart_ids = [c.id for c in rate_charts]

#     # Batch fetch RateGridModel rows, Prodata rows, and Formula configs concurrently
#     grid_stmt = select(RateGridModel).where(RateGridModel.rate_chart_id.in_(valid_chart_ids)).order_by(RateGridModel.row_number.asc())
#     prodata_stmt = select(ProdataRateRowModel).where(ProdataRateRowModel.rate_chart_id.in_(valid_chart_ids)).order_by(ProdataRateRowModel.row_number.asc())
#     formula_stmt = select(RateFormulaConfigModel).where(RateFormulaConfigModel.rate_chart_id.in_(valid_chart_ids))

#     grid_res, prodata_res, formula_res = await asyncio.gather(
#         session.execute(grid_stmt),
#         session.execute(prodata_stmt),
#         session.execute(formula_stmt),
#     )

#     # Group child rows by rate_chart_id
#     grid_rows_map: dict[UUID, list[RateGridModel]] = {}
#     for r in grid_res.scalars().all():
#         grid_rows_map.setdefault(r.rate_chart_id, []).append(r)

#     prodata_rows_map: dict[UUID, list[ProdataRateRowModel]] = {}
#     for r in prodata_res.scalars().all():
#         prodata_rows_map.setdefault(r.rate_chart_id, []).append(r)

#     formula_configs_map: dict[UUID, list[RateFormulaConfigModel]] = {}
#     for f in formula_res.scalars().all():
#         formula_configs_map.setdefault(f.rate_chart_id, []).append(f)

#     ratecharts_list = []
#     for chart in rate_charts:
#         g_rows = grid_rows_map.get(chart.id, [])
#         p_rows = prodata_rows_map.get(chart.id, [])
#         f_configs = formula_configs_map.get(chart.id, [])

#         ratecharts_list.append({
#             "id": str(chart.id),
#             "chart_name": chart.chart_name,
#             "chart_type": chart.chart_type.value if hasattr(chart.chart_type, 'value') else str(chart.chart_type),
#             "milk_type": chart.milk_type.value if hasattr(chart.milk_type, 'value') else str(chart.milk_type),
#             "calculation_type": chart.calculation_type.value if hasattr(chart.calculation_type, 'value') else str(chart.calculation_type),
#             "effective_from": chart.effective_from.isoformat() if chart.effective_from else None,
#             "effective_to": chart.effective_to.isoformat() if chart.effective_to else None,
#             "status": chart.status.value if hasattr(chart.status, 'value') else str(chart.status),
#             "created_by": str(chart.created_by) if chart.created_by else None,
#             "is_assigned": chart.id in assigned_ids,
#             "is_created_by_me": chart.created_by == owner_id,
#             "description": chart.description,
#             "grid_rows": [
#                 {
#                     "id": str(r.id),
#                     "row_number": r.row_number,
#                     "fat": float(r.fat),
#                     "snf": float(r.snf),
#                     "rate": float(r.rate),
#                 } for r in g_rows
#             ],
#             "prodata_rows": [
#                 {
#                     "id": str(r.id),
#                     "row_number": r.row_number,
#                     "fat_min": float(r.fat_min),
#                     "fat_max": float(r.fat_max),
#                     "snf_min": float(r.snf_min) if r.snf_min is not None else None,
#                     "snf_max": float(r.snf_max) if r.snf_max is not None else None,
#                     "fat_rate_per_kg": float(r.fat_rate_per_kg) if r.fat_rate_per_kg is not None else None,
#                     "snf_rate_per_kg": float(r.snf_rate_per_kg) if r.snf_rate_per_kg is not None else None,
#                     "snf_cutoff": float(r.snf_cutoff) if r.snf_cutoff is not None else None,
#                     "snf_deduction": float(r.snf_deduction) if r.snf_deduction is not None else None,
#                 } for r in p_rows
#             ],
#             "formula_configs": [
#                 {
#                     "id": str(f.id),
#                     "milk_type": f.milk_type.value if hasattr(f.milk_type, 'value') else str(f.milk_type),
#                     "cow_standard_fat": f.cow_standard_fat,
#                     "cow_standard_snf": f.cow_standard_snf,
#                     "cow_standard_rate": f.cow_standard_rate,
#                     "buffalo_standard_fat": f.buffalo_standard_fat,
#                     "buffalo_standard_snf": f.buffalo_standard_snf,
#                     "buffalo_standard_rate": f.buffalo_standard_rate,
#                     "cow_fat_percentage": f.cow_fat_percentage,
#                     "cow_snf_percentage": f.cow_snf_percentage,
#                     "buffalo_fat_percentage": f.buffalo_fat_percentage,
#                     "buffalo_snf_percentage": f.buffalo_snf_percentage,
#                 } for f in f_configs
#             ],
#             "updated_at": chart.updated_at.isoformat() if hasattr(chart, 'updated_at') and chart.updated_at else None,
#         })

#     return ratecharts_list


# async def fetch_vlccs_with_details_by_mcc(mcc_id: UUID, request: Request):
#     handler = GetHandler.vlcc_handler(request)
#     dtos: list[SubUserProfileSyncDto] = await handler.get_vlccs_with_details_by_mcc(mcc_id)
#     return dtos
#     # from dataclasses import asdict
#     # result = []
#     # for d in dtos:
#     #     dto_dict = asdict(d)
#     #     vlcc_data = dto_dict.get('vlcc', {})
#     #     addr_data = dto_dict.get('address')
#     #     bank_data = dto_dict.get('bank_account')

#     #     item = {
#     #         "id": str(vlcc_data.get('vlcc_id', '')),
#     #         "user_id": str(vlcc_data.get('vlcc_id', '')),
#     #         "code": str(vlcc_data.get('vlcc_code', '')),
#     #         "farmer_code": str(vlcc_data.get('vlcc_code', '')),
#     #         "vlcc_code": str(vlcc_data.get('vlcc_code', '')),
#     #         "uic_code": str(vlcc_data.get('uic_code', '') or ''),
#     #         "name": str(vlcc_data.get('vlcc_name', '')),
#     #         "mobile": str(vlcc_data.get('mobile', '') or ''),
#     #         "email": str(vlcc_data.get('email', '') or ''),
#     #         "contact_person": str(vlcc_data.get('vlcc_name', '')),
#     #         "entry_mode": str(vlcc_data.get('entry_mode', 'MANUAL')),
#     #         "route_code": vlcc_data.get('route_code'),
#     #         "assigned_chart_rank": vlcc_data.get('assigned_chart_rank', 1),
#     #         "is_active": True,
#     #         "user_profile": {
#     #             "name": str(vlcc_data.get('vlcc_name', '')),
#     #             "email": str(vlcc_data.get('email', '') or ''),
#     #             "mobile": str(vlcc_data.get('mobile', '') or ''),
#     #         },
#     #         "address": addr_data,
#     #         "bank_account": bank_data,
#     #     }
#     #     result.append(item)

#     # if not result:
#     #     session = request.app.state.application.container.database.session
#     #     user: CurrentUser | None = getattr(request.state, "user", None)
#     #     if user:
#     #         result = await fetch_vlccs_for_mcc(session, mcc_id, user.id)

#     # return result
    

# # =========================================================
# # MAIN SYNC API ENDPOINT (AUTO ROLE DETECT & DELTA SYNC)
# # =========================================================

# @router.get("")
# @router.get("/")
# async def auto_sync(
#     request: Request,
#     since: str | None = Query(default=None, description="ISO timestamp or unix timestamp for delta sync"),
# ):
#     print("WWWW: ", request)

#     """
#     Main Auto Data Sync API.

#     Detects logged in user's role:
#     - Role.VLCC: Syncs VLCC Settings, Ratecharts, Farmers.
#     - Role.MCC: Syncs MCC Settings, Ratecharts, VLCCs List.
#     - Performance: Ultra-fast parallel database execution with delta sync support (`since`).
#     """
#     user: CurrentUser | None = getattr(request.state, "user", None)
#     if not user:
#         raise HTTPException(status_code=401, detail="Unauthorized")

#     since_dt = parse_since(since)
#     server_now = datetime.now(timezone.utc)
#     server_time_iso = server_now.isoformat()

#     db_manager = request.app.state.application.container.database
#     session = db_manager.session

#     role_type = user.role_type

#     # =====================================================
#     # ROLE 1: VLCC SYNC (VLCC Settings + Ratecharts + Farmers)
#     # =====================================================
#     if role_type == Role.VLCC:
#         (vlcc_payload, vlcc_id, rank), ratecharts_list = await asyncio.gather(
#             fetch_vlcc_data(session, user.id),
#             fetch_ratecharts_data(session, user.id, role_type, since_dt),
#         )

#         farmers_list = await fetch_farmers_for_vlcc(
#             session=session,
#             vlcc_id=vlcc_id,
#             user_id=user.id,
#             since_dt=since_dt,
#         )

#         return JSONResponse(
#             content={
#                 "status": "success",
#                 "role": "VLCC",
#                 "server_time": server_time_iso,
#                 "synced_at": server_time_iso,
#                 "settings": vlcc_payload,
#                 "ratecharts": ratecharts_list,
#                 "farmers": farmers_list,
#                 "counts": {
#                     "farmers": len(farmers_list),
#                     "ratecharts": len(ratecharts_list),
#                 }
#             }
#         )

#     # =====================================================
#     # ROLE 2: MCC SYNC (MCC Settings + Ratecharts + VLCCs)
#     # =====================================================
#     elif role_type == Role.MCC:
#         (mcc_payload, mcc_id, route_code), ratecharts_list = await asyncio.gather(
#             fetch_mcc_data(session, user.id),
#             fetch_ratecharts_data(session, user.id, role_type, since_dt),
#         )

#         vlccs_list = await fetch_vlccs_with_details_by_mcc(
#             mcc_id=mcc_id,
#             request=request,
#         )

#         dd = []

#         for item in vlccs_list:
#             dd.append(
#                 SubUserProfileSyncDto()
#             )

#         return ORJSONResponse(
#             content=jsonable_encoder({
#                 "status": "success",
#                 "role": "MCC",
#                 "server_time": server_time_iso,
#                 "synced_at": server_time_iso,
#                 "settings": mcc_payload,
#                 "ratecharts": ratecharts_list,
#                 "vlccs": vlccs_list,
#                 "counts": {
#                     "vlccs": len(vlccs_list),
#                     "ratecharts": len(ratecharts_list),
#                 },
#             })
#         )

#     # =====================================================
#     # OTHER ROLES (ADMIN / SUPER ADMIN FALLBACK)
#     # =====================================================
#     else:
#         # Fallback for Admin / Super Admin: returns combined sync info
#         ratecharts_list = await fetch_ratecharts_data(session, user.id, role_type, since_dt)
#         farmers_list = await fetch_farmers_for_vlcc(session, None, user.id, since_dt)
#         vlccs_list = await fetch_vlccs_for_mcc(session, None, user.id, None, since_dt)

#         return JSONResponse(
#             content={
#                 "status": "success",
#                 "role": str(user.role),
#                 "server_time": server_time_iso,
#                 "synced_at": server_time_iso,
#                 "ratecharts": ratecharts_list,
#                 "farmers": farmers_list,
#                 "vlccs": vlccs_list,
#                 "counts": {
#                     "farmers": len(farmers_list),
#                     "vlccs": len(vlccs_list),
#                     "ratecharts": len(ratecharts_list),
#                 }
#             }
#         )


# # =========================================================
# # EXPLICIT VLCC SYNC ENDPOINT
# # =========================================================

# @router.get("/vlcc")
# async def vlcc_sync(
#     request: Request,
#     since: str | None = Query(default=None, description="ISO or unix timestamp for delta sync"),
# ):
#     """Explicit VLCC Sync Endpoint: Returns VLCC Settings, Ratecharts & Farmers."""
#     user: CurrentUser | None = getattr(request.state, "user", None)
#     if not user:
#         raise HTTPException(status_code=401, detail="Unauthorized")

#     since_dt = parse_since(since)
#     server_now = datetime.now(timezone.utc)
#     server_time_iso = server_now.isoformat()

#     session = request.app.state.application.container.database.session

#     (vlcc_payload, vlcc_id, rank), ratecharts_list = await asyncio.gather(
#         fetch_vlcc_data(session, user.id),
#         fetch_ratecharts_data(session, user.id, Role.VLCC, since_dt),
#     )

#     farmers_list = await fetch_farmers_for_vlcc(
#         session=session,
#         vlcc_id=vlcc_id,
#         user_id=user.id,
#         since_dt=since_dt,
#     )

#     return JSONResponse(
#         content={
#             "status": "success",
#             "role": "VLCC",
#             "server_time": server_time_iso,
#             "synced_at": server_time_iso,
#             "settings": vlcc_payload,
#             "ratecharts": ratecharts_list,
#             "farmers": farmers_list,
#             "counts": {
#                 "farmers": len(farmers_list),
#                 "ratecharts": len(ratecharts_list),
#             }
#         }
#     )


# # =========================================================
# # EXPLICIT MCC SYNC ENDPOINT
# # =========================================================

# @router.get("/mcc")
# async def mcc_sync(
#     request: Request,
#     since: str | None = Query(default=None, description="ISO or unix timestamp for delta sync"),
# ):
#     """Explicit MCC Sync Endpoint: Returns MCC Settings, Ratecharts & VLCCs list."""
#     user: CurrentUser | None = getattr(request.state, "user", None)
#     if not user:
#         raise HTTPException(status_code=401, detail="Unauthorized")

#     since_dt = parse_since(since)
#     server_now = datetime.now(timezone.utc)
#     server_time_iso = server_now.isoformat()

#     session = request.app.state.application.container.database.session

#     (mcc_payload, mcc_id, route_code), ratecharts_list = await asyncio.gather(
#         fetch_mcc_data(session, user.id),
#         fetch_ratecharts_data(session, user.id, Role.MCC, since_dt),
#     )

#     vlccs_list = await fetch_vlccs_for_mcc(
#         session=session,
#         mcc_id=mcc_id,
#         user_id=user.id,
#         route_code=route_code,
#         since_dt=since_dt,
#     )

#     return JSONResponse(
#         content={
#             "status": "success",
#             "role": "MCC",
#             "server_time": server_time_iso,
#             "synced_at": server_time_iso,
#             "settings": mcc_payload,
#             "ratecharts": ratecharts_list,
#             "vlccs": vlccs_list,
#             "counts": {
#                 "vlccs": len(vlccs_list),
#                 "ratecharts": len(ratecharts_list),
#             }
#         }
#     )


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
    farmer_handler = GetHandler.farmer_handler(request)
    farmer_dtos: list[SubUserProfileSyncDto] = await farmer_handler.get_farmers_detail_for_sync(vlcc_id=current_user.own_id, owner=current_user)
    
    vlcc = vlcc_full_detail.vlcc
    user= vlcc_full_detail.user
    bank_account= vlcc_full_detail.bank_account
    address= vlcc_full_detail.address
    setting= vlcc_full_detail.setting
    milk_quality_config= vlcc_full_detail.milk_quality_config
    ratecharts_list = await fetch_all_ratecharts(current_user.id, request)

    return VlccSyncDto(
        status=True,
        role=Role.VLCC,
        profile=ProfileSyncDto(
            id=vlcc.id,
            user_id=vlcc.user_id,
            name=user.name,
            email=user.email,
            mobile=user.mobile,
            code=vlcc.vlcc_code,
            profile_image=vlcc.profile_image or user.profile_image,
            uic_code=vlcc.uic_code,
            role=Role.VLCC,
            owner=None,
            route_code=vlcc.route_code,
            route_name=None,
            address=address,
            bank_account=bank_account,
        ),
        vlcc_info=VlccExtraInfoSyncDto(
            entry_mode=vlcc.entry_mode,
            soc_percentage=vlcc.soc_percentage,
            farmer_enabled=vlcc.farmer_enabled,
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

    if user.role_type not in [Role.VLCC, Role.MCC, Role.FARMER]:
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

    if user.role_type == Role.VLCC:
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

    
    if user.role_type not in [Role.VLCC, Role.MCC, Role.FARMER]:
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

    
    if user.role_type == Role.VLCC:
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

    elif user.role_type == Role.VLCC:
        data = await vlcc_data(request, user)

    elif user.role_type == Role.FARMER:
        data = await farmer_data(request, user)

    else:
        raise UnauthorizedException()

    return ORJSONResponse(
        content=jsonable_encoder(data)
    )