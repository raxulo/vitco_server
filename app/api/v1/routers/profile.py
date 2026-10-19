"""
Profile API Router

Provides logged-in user profile details (User info + Role-specific details like VLCC/MCC/Farmer, Address, Bank Account, Settings).

Python 3.13+
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.common.milk_quality.infrastructure.models import MilkQualityConfigModel

router = APIRouter(
    prefix="/profile",
    tags=["User Profile"],
)


@router.get("/me")
@router.get("/")
@router.get("")
async def get_my_profile(request: Request):
    """
    Get Logged-in User Profile Details.

    Returns complete user profile along with role-specific metadata:
    - VLCC: Vlcc master details, settings, quality config, address & bank info.
    - MCC: MCC master details, address & bank info.
    - Farmer: Farmer master details, address & bank info.
    - Admin / SubAdmin: Admin profile details.
    """
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session = request.app.state.application.container.database.session

    # Fetch User Model
    stmt_user = select(UserModel).where(UserModel.id == user_state.id)
    res_user = await session.execute(stmt_user)
    user_model = res_user.scalar_one_or_none()

    if not user_model:
        raise HTTPException(status_code=444, detail="User not found")

    user_data = {
        "id": str(user_model.id),
        "name": user_model.name,
        "email": user_model.email,
        "mobile": user_model.mobile,
        "role": user_model.role.value if hasattr(user_model.role, 'value') else str(user_model.role),
        "role_type": int(user_state.role_type),
        "profile_url": user_model.profile_url,
        "is_active": getattr(user_model, 'is_active', True),
        "is_verified": getattr(user_model, 'is_verified', True),
        "created_at": user_model.created_at.isoformat() if getattr(user_model, 'created_at', None) else None,
        "updated_at": user_model.updated_at.isoformat() if getattr(user_model, 'updated_at', None) else None,
    }

    role_details: dict[str, Any] | None = None

    # =========================================================
    # ROLE: VLCC
    # =========================================================
    if user_state.role_type == Role.VLCC:
        stmt_vlcc = (
            select(
                VlccModel,
                AddressModel,
                BankAccountModel
            )
            .where(VlccModel.user_id == user_state.id)
            .outerjoin(AddressModel, AddressModel.id == VlccModel.address_id)
            .outerjoin(BankAccountModel, BankAccountModel.id == VlccModel.bank_account_id)
        )
        res_vlcc = await session.execute(stmt_vlcc)
        row = res_vlcc.first()

        if row:
            vlcc, addr, bank = row
            role_details = {
                "vlcc_id": str(vlcc.id),
                "vlcc_code": vlcc.vlcc_code,
                "uic_code": vlcc.uic_code,
                "name": vlcc.name,
                "contact_person": vlcc.contact_person,
                "entry_mode": vlcc.entry_mode.value if hasattr(vlcc.entry_mode, 'value') else str(vlcc.entry_mode),
                "soc_percentage": float(vlcc.soc_percentage) if vlcc.soc_percentage is not None else 0.0,
                "farmer_enabled": bool(vlcc.farmer_enabled),
                "assigned_chart_rank": int(vlcc.assigned_chart_rank or 1),
                "route_code": vlcc.route_code,
                "is_active": bool(vlcc.is_active),
                "address": {
                    "id": str(addr.id),
                    "line": addr.line,
                    "city": addr.city,
                    "state": addr.state,
                    "pincode": addr.pincode,
                } if addr else None,
                "bank_account": {
                    "id": str(bank.id),
                    "bank_name": bank.bank_name,
                    "account_holder": bank.account_holder,
                    "account_number": bank.account_number,
                    "ifsc_code": bank.ifsc_code,
                    "upi_id": bank.upi_id,
                } if bank else None,
            }

    # =========================================================
    # ROLE: MCC
    # =========================================================
    elif user_state.role_type == Role.MCC:
        stmt_mcc = (
            select(
                MccModel,
                AddressModel,
                BankAccountModel
            )
            .where(MccModel.user_id == user_state.id)
            .outerjoin(AddressModel, AddressModel.id == MccModel.address_id)
            .outerjoin(BankAccountModel, BankAccountModel.id == MccModel.bank_account_id)
        )
        res_mcc = await session.execute(stmt_mcc)
        row = res_mcc.first()

        if row:
            mcc, addr, bank = row
            role_details = {
                "mcc_id": str(mcc.id),
                "code": mcc.code,
                "name": mcc.name,
                "mcc_type": mcc.mcc_type.value if hasattr(mcc.mcc_type, 'value') else str(mcc.mcc_type),
                "route_code": mcc.route_code,
                "sample_start": mcc.sample_start,
                "sample_end": getattr(mcc, 'sample_end', None),
                "address": {
                    "id": str(addr.id),
                    "line": addr.line,
                    "city": addr.city,
                    "state": addr.state,
                    "pincode": addr.pincode,
                } if addr else None,
                "bank_account": {
                    "id": str(bank.id),
                    "bank_name": bank.bank_name,
                    "account_holder": bank.account_holder,
                    "account_number": bank.account_number,
                    "ifsc_code": bank.ifsc_code,
                    "upi_id": bank.upi_id,
                } if bank else None,
            }

    # =========================================================
    # ROLE: FARMER
    # =========================================================
    elif user_state.role_type == Role.FARMER:
        stmt_farmer = (
            select(
                FarmerModel,
                AddressModel,
                BankAccountModel
            )
            .where(FarmerModel.user_id == user_state.id)
            .outerjoin(AddressModel, AddressModel.id == FarmerModel.address_id)
            .outerjoin(BankAccountModel, BankAccountModel.id == FarmerModel.bank_account_id)
        )
        res_farmer = await session.execute(stmt_farmer)
        row = res_farmer.first()

        if row:
            farmer, addr, bank = row
            role_details = {
                "farmer_id": str(farmer.id),
                "farmer_code": farmer.farmer_code,
                "vlcc_id": str(farmer.vlcc_id) if farmer.vlcc_id else None,
                "address": {
                    "id": str(addr.id),
                    "line": addr.line,
                    "city": addr.city,
                    "state": addr.state,
                    "pincode": addr.pincode,
                } if addr else None,
                "bank_account": {
                    "id": str(bank.id),
                    "bank_name": bank.bank_name,
                    "account_holder": bank.account_holder,
                    "account_number": bank.account_number,
                    "ifsc_code": bank.ifsc_code,
                    "upi_id": bank.upi_id,
                } if bank else None,
            }

    return JSONResponse(
        content={
            "status": "success",
            "user": user_data,
            "details": role_details,
        }
    )
