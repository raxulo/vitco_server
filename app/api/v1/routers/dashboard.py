"""
Dashboard API Router

Delivers role-based dashboard statistics, metrics, and recent activity
for logged-in VLCC, MCC, Farmer, and Admin users.

Python 3.13+
"""
from app.api.v1.schemas.dashboard import (
    CollectionPaymentSummaryData,
    DashboardDataResponse,
    ParticipateSummaryData,
    PaymentSummaryData,
    ShiftSummaryData,
)
from app.modules.payments.application.dto import PaymentCollectionSummaryViaPeriodDto
from app.modules.common.settings.domain.entities import Settings
from app.modules.common.settings.domain.exceptions import SettingsNotFoundError
from app.modules.dependencies import GetHandler
from zoneinfo import ZoneInfo
from datetime import timedelta
from enum import StrEnum
from fastapi import Query

import asyncio
from datetime import datetime, time, timezone
from typing import Any, List
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, and_, or_

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.api.v1.schemas.dashboard import (
    DashboardResponse,
    RoleDashboardData,
    MetricCard,
    ShiftSummary,
    MilkTypeSummary,
    RecentCollectionItem,
)

from app.modules.collections.mcc_collection.domain.enums import CollectionShift, MilkType
from app.core.clock import now_ist, now_naive_ist
IST = ZoneInfo("Asia/Kolkata")

def format_shift_str(shift: Any) -> str:
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

def format_milk_type_str(milk_type: Any) -> str:
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

def parse_shift_param(shift: Any) -> Any:
    if shift is None or str(shift).strip() == "" or str(shift).upper() == "ALL":
        return None
    s_upper = str(shift).upper().strip()
    if s_upper in ("0", "MORNING"):
        return CollectionShift.MORNING
    if s_upper in ("1", "EVENING"):
        return CollectionShift.EVENING
    return None

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard API"],
)


def get_day_and_month_bounds() -> tuple[datetime, datetime]:
    """Start of today and of the current month in IST (naive, like stored collection times)."""
    now = now_naive_ist()
    today_start = datetime(now.year, now.month, now.day)
    month_start = datetime(now.year, now.month, 1)
    return today_start, month_start


# =========================================================
# HELPER: VLCC DASHBOARD COMPUTATION
# =========================================================

async def build_vlcc_dashboard(session, user: CurrentUser, shift: Any = None) -> RoleDashboardData:
    today_start, month_start = get_day_and_month_bounds()
    s_enum = parse_shift_param(shift)

    # Find VLCC Record
    stmt_vlcc = select(VlccModel.id).where(VlccModel.user_id == user.id)
    res_vlcc = await session.execute(stmt_vlcc)
    vlcc_id = res_vlcc.scalar_one_or_none()

    if not vlcc_id:
        stmt_vlcc_alt = select(VlccModel.id).where(VlccModel.created_by == user.id)
        res_vlcc_alt = await session.execute(stmt_vlcc_alt)
        vlcc_id = res_vlcc_alt.scalar_one_or_none()

    # 1. Total Farmers Count
    farmer_count_stmt = select(func.count(FarmerModel.id))
    if vlcc_id:
        farmer_count_stmt = farmer_count_stmt.where(or_(FarmerModel.vlcc_id == vlcc_id, FarmerModel.created_by == user.id))
    else:
        farmer_count_stmt = farmer_count_stmt.where(FarmerModel.created_by == user.id)

    # 2. Today's Totals (Qty, Amount, Avg Fat, Avg SNF)
    today_stmt = (
        select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amt"),
            func.coalesce(func.avg(VlccCollectionModel.fat_percent), 0.0).label("avg_fat"),
            func.coalesce(func.avg(VlccCollectionModel.snf_percent), 0.0).label("avg_snf"),
        )
        .where(VlccCollectionModel.collected_at >= today_start)
    )
    if vlcc_id:
        today_stmt = today_stmt.where(VlccCollectionModel.vlcc_id == vlcc_id)
    if s_enum is not None:
        today_stmt = today_stmt.where(
            or_(
                VlccCollectionModel.shift == s_enum,
                VlccCollectionModel.shift == s_enum.value,
                VlccCollectionModel.shift == s_enum.name,
            )
        )

    # 3. Monthly Totals
    month_stmt = (
        select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amt"),
        )
        .where(VlccCollectionModel.collected_at >= month_start)
    )
    if vlcc_id:
        month_stmt = month_stmt.where(VlccCollectionModel.vlcc_id == vlcc_id)

    # 4. Shift Breakdown Today
    shift_stmt = (
        select(
            VlccCollectionModel.shift,
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("amt"),
            func.count(VlccCollectionModel.id).label("cnt"),
            func.coalesce(func.avg(VlccCollectionModel.fat_percent), 0.0).label("avg_fat"),
            func.coalesce(func.avg(VlccCollectionModel.snf_percent), 0.0).label("avg_snf"),
        )
        .where(VlccCollectionModel.collected_at >= today_start)
        .group_by(VlccCollectionModel.shift)
    )
    if vlcc_id:
        shift_stmt = shift_stmt.where(VlccCollectionModel.vlcc_id == vlcc_id)
    if s_enum is not None:
        shift_stmt = shift_stmt.where(
            or_(
                VlccCollectionModel.shift == s_enum,
                VlccCollectionModel.shift == s_enum.value,
                VlccCollectionModel.shift == s_enum.name,
            )
        )

    # 5. Milk Type Breakdown Today
    milk_type_stmt = (
        select(
            VlccCollectionModel.milk_type,
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("amt"),
            func.count(VlccCollectionModel.id).label("cnt"),
        )
        .where(VlccCollectionModel.collected_at >= today_start)
        .group_by(VlccCollectionModel.milk_type)
    )
    if vlcc_id:
        milk_type_stmt = milk_type_stmt.where(VlccCollectionModel.vlcc_id == vlcc_id)
    if s_enum is not None:
        milk_type_stmt = milk_type_stmt.where(
            or_(
                VlccCollectionModel.shift == s_enum,
                VlccCollectionModel.shift == s_enum.value,
                VlccCollectionModel.shift == s_enum.name,
            )
        )

    # 6. Recent 10 Collections
    recent_stmt = (
        select(
            VlccCollectionModel,
            UserModel.name.label("farmer_name"),
            FarmerModel.farmer_code
        )
        .join(FarmerModel, FarmerModel.id == VlccCollectionModel.farmer_id)
        .join(UserModel, UserModel.id == FarmerModel.user_id)
    )
    if vlcc_id:
        recent_stmt = recent_stmt.where(VlccCollectionModel.vlcc_id == vlcc_id)

    recent_stmt = recent_stmt.order_by(VlccCollectionModel.collected_at.desc()).limit(10)

    # Execute all queries concurrently
    f_cnt_res, today_res, month_res, shift_res, milk_res, recent_res = await asyncio.gather(
        session.execute(farmer_count_stmt),
        session.execute(today_stmt),
        session.execute(month_stmt),
        session.execute(shift_stmt),
        session.execute(milk_type_stmt),
        session.execute(recent_stmt),
    )

    total_farmers = f_cnt_res.scalar() or 0

    t_row = today_res.first()
    today_qty = float(t_row.total_qty) if t_row else 0.0
    today_amt = float(t_row.total_amt) if t_row else 0.0
    avg_fat = float(t_row.avg_fat) if t_row else 0.0
    avg_snf = float(t_row.avg_snf) if t_row else 0.0

    m_row = month_res.first()
    month_qty = float(m_row.total_qty) if m_row else 0.0
    month_amt = float(m_row.total_amt) if m_row else 0.0

    shifts_list = []
    for s_row in shift_res.all():
        shifts_list.append(
            ShiftSummary(
                shift=format_shift_str(s_row.shift),
                total_quantity=float(s_row.qty),
                total_amount=float(s_row.amt),
                entry_count=int(s_row.cnt),
                avg_fat=round(float(s_row.avg_fat), 2),
                avg_snf=round(float(s_row.avg_snf), 2),
            )
        )

    milk_types_list = []
    for m_row_item in milk_res.all():
        milk_types_list.append(
            MilkTypeSummary(
                milk_type=format_milk_type_str(m_row_item.milk_type),
                total_quantity=float(m_row_item.qty),
                total_amount=float(m_row_item.amt),
                entry_count=int(m_row_item.cnt),
            )
        )

    recent_items = []
    for row_item in recent_res.all():
        c = row_item.VlccCollectionModel
        recent_items.append(
            RecentCollectionItem(
                id=str(c.id),
                farmer_name=row_item.farmer_name or "",
                farmer_code=str(row_item.farmer_code) if row_item.farmer_code else None,
                shift=format_shift_str(c.shift),
                milk_type=format_milk_type_str(c.milk_type),
                quantity=float(c.quantity),
                fat=float(c.fat_percent or 0.0),
                snf=float(c.snf_percent or 0.0),
                rate=float(c.rate_per_unit or 0.0),
                total_amount=float(c.total_amount),
                collected_at=c.collected_at.isoformat() if c.collected_at else "",
            )
        )

    cards = [
        MetricCard(title="Registered Farmers", value=total_farmers, subtitle="Active Suppliers", icon="people"),
        MetricCard(title="Today Collection", value=f"{today_qty:.2f} L", subtitle=f"₹ {today_amt:.2f}", icon="local_drink"),
        MetricCard(title="Monthly Collection", value=f"{month_qty:.2f} L", subtitle=f"₹ {month_amt:.2f}", icon="calendar_today"),
        MetricCard(title="Avg Quality Today", value=f"{avg_fat:.1f}% FAT", subtitle=f"{avg_snf:.1f}% SNF", icon="analytics"),
    ]

    return RoleDashboardData(
        cards=cards,
        today_quantity=today_qty,
        today_amount=today_amt,
        monthly_quantity=month_qty,
        monthly_amount=month_amt,
        avg_fat=round(avg_fat, 2),
        avg_snf=round(avg_snf, 2),
        shifts=shifts_list,
        milk_types=milk_types_list,
        recent_collections=recent_items,
    )


# =========================================================
# HELPER: MCC DASHBOARD COMPUTATION
# =========================================================

async def build_mcc_dashboard(session, user: CurrentUser, shift: Any = None) -> RoleDashboardData:
    today_start, month_start = get_day_and_month_bounds()
    s_enum = parse_shift_param(shift)

    # Find MCC record
    stmt_mcc = select(MccModel).where(MccModel.user_id == user.id)
    res_mcc = await session.execute(stmt_mcc)
    mcc = res_mcc.scalar_one_or_none()

    mcc_id = mcc.id if mcc else None
    route_code = mcc.route_code if mcc else None

    # Total Assigned VLCCs
    vlcc_count_stmt = select(func.count(VlccModel.id))
    if route_code is not None:
        vlcc_count_stmt = vlcc_count_stmt.where(or_(VlccModel.created_by == user.id, VlccModel.route_code == route_code))
    else:
        vlcc_count_stmt = vlcc_count_stmt.where(VlccModel.created_by == user.id)

    # Today's Received Milk (from MccCollectionModel or VlccCollectionModel)
    today_stmt = (
        select(
            func.coalesce(func.sum(MccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(MccCollectionModel.total_amount), 0.0).label("total_amt"),
            func.coalesce(func.avg(MccCollectionModel.fat_percent), 0.0).label("avg_fat"),
            func.coalesce(func.avg(MccCollectionModel.snf_percent), 0.0).label("avg_snf"),
        )
        .where(MccCollectionModel.collected_at >= today_start)
    )
    if mcc_id:
        today_stmt = today_stmt.where(MccCollectionModel.mcc_id == mcc_id)
    if s_enum is not None:
        today_stmt = today_stmt.where(
            or_(
                MccCollectionModel.shift == s_enum,
                MccCollectionModel.shift == s_enum.value,
                MccCollectionModel.shift == s_enum.name,
            )
        )

    # Monthly Totals
    month_stmt = (
        select(
            func.coalesce(func.sum(MccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(MccCollectionModel.total_amount), 0.0).label("total_amt"),
        )
        .where(MccCollectionModel.collected_at >= month_start)
    )
    if mcc_id:
        month_stmt = month_stmt.where(MccCollectionModel.mcc_id == mcc_id)

    recent_stmt = (
        select(
            MccCollectionModel,
            VlccModel.name.label("vlcc_name")
        )
        .outerjoin(VlccModel, VlccModel.id == MccCollectionModel.vlcc_id)
    )
    if mcc_id:
        recent_stmt = recent_stmt.where(MccCollectionModel.mcc_id == mcc_id)

    recent_stmt = recent_stmt.order_by(MccCollectionModel.collected_at.desc()).limit(10)

    vlcc_res, today_res, month_res, recent_res = await asyncio.gather(
        session.execute(vlcc_count_stmt),
        session.execute(today_stmt),
        session.execute(month_stmt),
        session.execute(recent_stmt),
    )

    total_vlccs = vlcc_res.scalar() or 0

    t_row = today_res.first()
    today_qty = float(t_row.total_qty) if t_row else 0.0
    today_amt = float(t_row.total_amt) if t_row else 0.0
    avg_fat = float(t_row.avg_fat) if t_row else 0.0
    avg_snf = float(t_row.avg_snf) if t_row else 0.0

    m_row = month_res.first()
    month_qty = float(m_row.total_qty) if m_row else 0.0
    month_amt = float(m_row.total_amt) if m_row else 0.0

    recent_items = []
    for row_item in recent_res.all():
        c = row_item.MccCollectionModel
        recent_items.append(
            RecentCollectionItem(
                id=str(c.id),
                vlcc_name=row_item.vlcc_name or "VLCC Center",
                shift=format_shift_str(c.shift),
                milk_type=format_milk_type_str(c.milk_type),
                quantity=float(c.quantity),
                fat=float(c.fat_percent or 0.0),
                snf=float(c.snf_percent or 0.0),
                rate=float(c.rate_per_unit or 0.0),
                total_amount=float(c.total_amount),
                collected_at=c.collected_at.isoformat() if c.collected_at else "",
            )
        )

    cards = [
        MetricCard(title="Connected VLCCs", value=total_vlccs, subtitle="Active Milk Centers", icon="store"),
        MetricCard(title="Today Received", value=f"{today_qty:.2f} L", subtitle=f"₹ {today_amt:.2f}", icon="local_shipping"),
        MetricCard(title="Monthly Received", value=f"{month_qty:.2f} L", subtitle=f"₹ {month_amt:.2f}", icon="calendar_today"),
        MetricCard(title="Avg Quality Today", value=f"{avg_fat:.1f}% FAT", subtitle=f"{avg_snf:.1f}% SNF", icon="analytics"),
    ]

    return RoleDashboardData(
        cards=cards,
        today_quantity=today_qty,
        today_amount=today_amt,
        monthly_quantity=month_qty,
        monthly_amount=month_amt,
        avg_fat=round(avg_fat, 2),
        avg_snf=round(avg_snf, 2),
        recent_collections=recent_items,
    )


# =========================================================
# HELPER: FARMER DASHBOARD COMPUTATION
# =========================================================

async def build_farmer_dashboard(session, user: CurrentUser) -> RoleDashboardData:
    today_start, month_start = get_day_and_month_bounds()

    stmt_farmer = select(FarmerModel.id).where(FarmerModel.user_id == user.id)
    res_farmer = await session.execute(stmt_farmer)
    farmer_id = res_farmer.scalar_one_or_none()

    if not farmer_id:
        return RoleDashboardData(
            cards=[MetricCard(title="Status", value="Not Linked", subtitle="Contact VLCC", icon="info")]
        )

    today_stmt = (
        select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amt"),
            func.coalesce(func.avg(VlccCollectionModel.fat_percent), 0.0).label("avg_fat"),
            func.coalesce(func.avg(VlccCollectionModel.snf_percent), 0.0).label("avg_snf"),
        )
        .where(VlccCollectionModel.farmer_id == farmer_id, VlccCollectionModel.collected_at >= today_start)
    )

    month_stmt = (
        select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amt"),
        )
        .where(VlccCollectionModel.farmer_id == farmer_id, VlccCollectionModel.collected_at >= month_start)
    )

    recent_stmt = (
        select(VlccCollectionModel)
        .where(VlccCollectionModel.farmer_id == farmer_id)
        .order_by(VlccCollectionModel.collected_at.desc())
        .limit(10)
    )

    today_res, month_res, recent_res = await asyncio.gather(
        session.execute(today_stmt),
        session.execute(month_stmt),
        session.execute(recent_stmt),
    )

    t_row = today_res.first()
    today_qty = float(t_row.total_qty) if t_row else 0.0
    today_amt = float(t_row.total_amt) if t_row else 0.0
    avg_fat = float(t_row.avg_fat) if t_row else 0.0
    avg_snf = float(t_row.avg_snf) if t_row else 0.0

    m_row = month_res.first()
    month_qty = float(m_row.total_qty) if m_row else 0.0
    month_amt = float(m_row.total_amt) if m_row else 0.0

    recent_items = []
    for c in recent_res.scalars().all():
        recent_items.append(
            RecentCollectionItem(
                id=str(c.id),
                shift=format_shift_str(c.shift),
                milk_type=format_milk_type_str(c.milk_type),
                quantity=float(c.quantity),
                fat=float(c.fat_percent or 0.0),
                snf=float(c.snf_percent or 0.0),
                rate=float(c.rate_per_unit or 0.0),
                total_amount=float(c.total_amount),
                collected_at=c.collected_at.isoformat() if c.collected_at else "",
            )
        )

    cards = [
        MetricCard(title="Today Milk Supply", value=f"{today_qty:.2f} L", subtitle=f"₹ {today_amt:.2f}", icon="local_drink"),
        MetricCard(title="Monthly Milk Supply", value=f"{month_qty:.2f} L", subtitle=f"₹ {month_amt:.2f}", icon="calendar_today"),
        MetricCard(title="Avg FAT Today", value=f"{avg_fat:.1f}%", subtitle="Fat Percentage", icon="analytics"),
        MetricCard(title="Avg SNF Today", value=f"{avg_snf:.1f}%", subtitle="SNF Percentage", icon="analytics"),
    ]

    return RoleDashboardData(
        cards=cards,
        today_quantity=today_qty,
        today_amount=today_amt,
        monthly_quantity=month_qty,
        monthly_amount=month_amt,
        avg_fat=round(avg_fat, 2),
        avg_snf=round(avg_snf, 2),
        recent_collections=recent_items,
    )


# =========================================================
# HELPER: ADMIN DASHBOARD COMPUTATION
# =========================================================

async def build_admin_dashboard(session, user: CurrentUser) -> RoleDashboardData:
    today_start, month_start = get_day_and_month_bounds()

    mcc_count_stmt = select(func.count(MccModel.id))
    vlcc_count_stmt = select(func.count(VlccModel.id))
    farmer_count_stmt = select(func.count(FarmerModel.id))

    today_stmt = (
        select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amt"),
            func.coalesce(func.avg(VlccCollectionModel.fat_percent), 0.0).label("avg_fat"),
            func.coalesce(func.avg(VlccCollectionModel.snf_percent), 0.0).label("avg_snf"),
        )
        .where(VlccCollectionModel.collected_at >= today_start)
    )

    month_stmt = (
        select(
            func.coalesce(func.sum(VlccCollectionModel.quantity), 0.0).label("total_qty"),
            func.coalesce(func.sum(VlccCollectionModel.total_amount), 0.0).label("total_amt"),
        )
        .where(VlccCollectionModel.collected_at >= month_start)
    )

    mcc_res, vlcc_res, farmer_res, today_res, month_res = await asyncio.gather(
        session.execute(mcc_count_stmt),
        session.execute(vlcc_count_stmt),
        session.execute(farmer_count_stmt),
        session.execute(today_stmt),
        session.execute(month_stmt),
    )

    total_mccs = mcc_res.scalar() or 0
    total_vlccs = vlcc_res.scalar() or 0
    total_farmers = farmer_res.scalar() or 0

    t_row = today_res.first()
    today_qty = float(t_row.total_qty) if t_row else 0.0
    today_amt = float(t_row.total_amt) if t_row else 0.0
    avg_fat = float(t_row.avg_fat) if t_row else 0.0
    avg_snf = float(t_row.avg_snf) if t_row else 0.0

    m_row = month_res.first()
    month_qty = float(m_row.total_qty) if m_row else 0.0
    month_amt = float(m_row.total_amt) if m_row else 0.0

    cards = [
        MetricCard(title="Total MCCs", value=total_mccs, subtitle="Active Centers", icon="account_balance"),
        MetricCard(title="Total VLCCs", value=total_vlccs, subtitle="Active Collection Units", icon="store"),
        MetricCard(title="Total Farmers", value=total_farmers, subtitle="Registered Suppliers", icon="people"),
        MetricCard(title="Today's Collection", value=f"{today_qty:.2f} L", subtitle=f"₹ {today_amt:.2f}", icon="local_drink"),
    ]

    return RoleDashboardData(
        cards=cards,
        today_quantity=today_qty,
        today_amount=today_amt,
        monthly_quantity=month_qty,
        monthly_amount=month_amt,
        avg_fat=round(avg_fat, 2),
        avg_snf=round(avg_snf, 2),
    )


# =========================================================
# MAIN DASHBOARD ENDPOINT
# =========================================================

class PeriodType(StrEnum):
    CURRENT = "now"
    MORNING = "mo"
    EVENING = "ev"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1m"
    HALF_YEAR = "6m"
    YEAR = "1y"


def map_period_to_collection_shift(period_type: PeriodType) -> CollectionShift | None:
    if period_type == PeriodType.MORNING:
        return CollectionShift.MORNING
    if period_type == PeriodType.EVENING:
        return CollectionShift.EVENING
    return None


def get_shift_datetime_range(
    period: PeriodType,
    settings: Settings,
    now: datetime,
) -> tuple[datetime | None, datetime | None, PeriodType]:
    today = now.date()

    if period == PeriodType.CURRENT:
        now_time = now.time()
        morning_end = time.fromisoformat(settings.morning_collection_end)

        if now_time < morning_end:
            period = PeriodType.MORNING
        else:
            period = PeriodType.EVENING

    if period == PeriodType.MORNING:
        start_time = time.fromisoformat(settings.morning_collection_start)
        end_time = time.fromisoformat(settings.morning_collection_end)
    elif period == PeriodType.EVENING:
        start_time = time.fromisoformat(settings.evening_collection_start)
        end_time = time.fromisoformat(settings.evening_collection_end)
    else:
        return None, None, period

    date_from = datetime.combine(today, start_time, tzinfo=IST)
    date_to = datetime.combine(today, end_time, tzinfo=IST)

    return date_from, date_to, period


def get_period_bounds(
    period: PeriodType,
    setting: Settings,
) -> tuple[datetime, datetime, PeriodType]:
    now_datetime = now_ist()
    full_day_now = now_datetime.replace(hour=0, minute=0, second=0, microsecond=0)

    if period in (PeriodType.MORNING, PeriodType.EVENING, PeriodType.CURRENT):
        date_from, date_to, active_shift = get_shift_datetime_range(
            period=period,
            settings=setting,
            now=now_datetime,
        )
        if date_from and date_to:
            return date_from, date_to, active_shift

    if period == PeriodType.DAY:
        date_from = full_day_now
        date_to = full_day_now + timedelta(days=1)
    elif period == PeriodType.WEEK:
        date_from = full_day_now - timedelta(weeks=1)
        date_to = now_datetime
    elif period == PeriodType.MONTH:
        date_from = full_day_now - timedelta(days=30)
        date_to = now_datetime
    elif period == PeriodType.HALF_YEAR:
        date_from = full_day_now - timedelta(days=180)
        date_to = now_datetime
    elif period == PeriodType.YEAR:
        date_from = full_day_now - timedelta(days=365)
        date_to = now_datetime
    else:
        date_from = full_day_now
        date_to = now_datetime

    return date_from, date_to, period


def get_payment_title(period: PeriodType) -> str:
    title_map = {
        PeriodType.CURRENT: "Current Shift Payment",
        PeriodType.MORNING: "Today - Morning Payment",
        PeriodType.EVENING: "Today - Evening Payment",
        PeriodType.DAY: "Today's Payment",
        PeriodType.WEEK: "This Week Payment",
        PeriodType.MONTH: "This Month Payment",
        PeriodType.HALF_YEAR: "Last 6 Months Payment",
        PeriodType.YEAR: "Last Year Payment",
    }
    return title_map.get(period, "Today's Payment")


def create_metric_cards(summary: Any) -> list[MetricCard]:
    return [
        MetricCard(
            title="Milk Supply",
            value=f"{summary.total_quantity:.2f} L",
            subtitle="Total Milk Supply",
            icon="local_drink",
        ),
        MetricCard(
            title="Total Collection",
            value=f"₹ {summary.total_amount:.2f}",
            subtitle="Total Amount",
            icon="local_drink",
        ),
        MetricCard(
            title="Avg Quality",
            value=f"{summary.avg_fat:.1f}% FAT",
            subtitle=f"{summary.avg_snf:.1f}% SNF",
            icon="analytics",
        ),
        MetricCard(
            title="Avg Rate",
            value=f"{summary.avg_rate:.2f}",
            subtitle="Rate Per Litre",
            icon="analytics",
        ),
    ]

@router.get("/me")
@router.get("/")
@router.get("")
async def get_dashboard_data(
    request: Request,
    period: PeriodType = Query(default=PeriodType.CURRENT),
):
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    metrics_cards = []
    participate_data = None
    setting_handler = GetHandler.settings_handler(request)
    try:
        setting: Settings = await setting_handler.get_by_user_id(
            user_id=user_state.id,
            user_type=user_state.role_type,
        )
    except SettingsNotFoundError:
        setting = Settings(id=uuid4())

    date_from, date_to, period_type = get_period_bounds(period=period, setting=setting)

    # period_is_current_shift = ((period == PeriodType.MORNING and current_shift == CollectionShift.MORNING)
    #     or (period == PeriodType.EVENING and current_shift == CollectionShift.EVENING))

    payment_service = GetHandler.payment_posting_service(request)
    payment_ledger: PaymentCollectionSummaryViaPeriodDto = await payment_service.get_payment_summary_by_period(
        user_id=user_state.id, 
        start_date=date_from, 
        end_date=date_to
    )
    collection_payment_summary=CollectionPaymentSummaryData(
        title=get_payment_title(period),
        total=payment_ledger.total_collection_amount,
        pending=payment_ledger.total_debit_amount,
        paid=payment_ledger.total_credit_amount,
    )

    balance = await payment_service.get_user_balance(user_state.id)
    raw_outstanding = await payment_service.get_user_outstanding(user_state.id)

    total_to_collect = 0.0
    total_to_pay = 0.0

    for item in raw_outstanding:
        val = float(item.balance)

        if val > 0:
            total_to_collect += val
        elif val < 0:
            total_to_pay += abs(val)
            
    payment_summary = PaymentSummaryData(
        title= "Account Data",
        balance=balance,
        to_pay=total_to_pay,
        to_collect=total_to_collect,
    )
    current_shift_collection_payment_summary:ShiftSummaryData = None
    # if period not in (PeriodType.MORNING, PeriodType.EVENING):
    #     date_from, date_to = get_period_bounds(
    #         period=PeriodType.CURRENT,
    #         setting=setting,
    #     )
    #     current_shift_payment_ledger: PaymentCollectionSummaryViaPeriodDto = await payment_service.get_payment_summary_by_period(
    #         user_id=user_state.id, 
    #         start_date=date_from, 
    #         end_date=date_to
    #     )
    
    #     current_shift_collection_payment_summary=CollectionPaymentSummaryData(
    #         title=get_payment_title(PeriodType.CURRENT),
    #         total=current_shift_payment_ledger.total_collection_amount,
    #         pending=current_shift_payment_ledger.total_credit_amount,
    #         paid=current_shift_payment_ledger.total_debit_amount,
    #     )
    collection_shift = map_period_to_collection_shift(period)
    if user_state.role_type == Role.MCC:
        mcc_collection_service = GetHandler.mcc_collection_handler(request)
        mcc_summary = await mcc_collection_service.get_collection_summary(
            date_from=date_from,
            date_to=date_to,
            owner=user_state,
            shift=collection_shift,
        )
        total_vlccs = await GetHandler.vlcc_handler(request).count(owner=user_state)
        vlcc_supplied_per = int(round((mcc_summary.active_users / total_vlccs) * 100)) if total_vlccs > 0 else 0
        participate_data = ParticipateSummaryData(
            title="VLCCs Participation",
            role=Role.VLCC,
            count=total_vlccs,
            pending=max(0, total_vlccs - mcc_summary.active_users),
            accepted=mcc_summary.active_users,
            supplied_per=vlcc_supplied_per,
        )
        metrics_cards = create_metric_cards(mcc_summary)

    elif user_state.role_type == Role.VLCC:
        vlcc_collection_service = GetHandler.vlcc_collection_handler(request)
        vlcc_summary = await vlcc_collection_service.get_collection_summary(
            date_from=date_from,
            date_to=date_to,
            owner=user_state,
            shift=collection_shift,
        )
        total_farmers = await GetHandler.farmer_handler(request).count(owner=user_state)
        farmer_supplied_per = int(round((vlcc_summary.active_users / total_farmers) * 100)) if total_farmers > 0 else 0
        participate_data = ParticipateSummaryData(
            title="Farmers Participation",
            role=Role.FARMER,
            count=total_farmers,
            pending=max(0, total_farmers - vlcc_summary.active_users),
            accepted=vlcc_summary.active_users,
            supplied_per=farmer_supplied_per,
        )
        metrics_cards = create_metric_cards(vlcc_summary)

    elif user_state.role_type == Role.VLCC_FARMER:
        mcc_collection_service = GetHandler.mcc_collection_handler(request)
        mcc_summary = await mcc_collection_service.get_collection_summary(
            date_from=date_from,
            date_to=date_to,
            owner=user_state,
            shift=collection_shift,
        )
        metrics_cards = create_metric_cards(mcc_summary)

    elif user_state.role_type == Role.FARMER:
        vlcc_collection_service = GetHandler.vlcc_collection_handler(request)
        vlcc_summary = await vlcc_collection_service.get_collection_summary(
            date_from=date_from,
            date_to=date_to,
            owner=user_state,
            shift=collection_shift,
        )
        metrics_cards = create_metric_cards(vlcc_summary)

    return DashboardDataResponse(
        status=True,
        message="Dashboard data fetched successfully",
        synced_time=now_ist().strftime("%H:%M"),
        role=user_state.role_type,
        collection_payment_summary=collection_payment_summary,
        payment_summary=payment_summary,
        current_shift_summary=None,
        participate=participate_data,
        cards=metrics_cards,
    )



