"""
Auth Web Controller
"""

import logging

from app.modules.administration.application import permission
from app.modules.administration.application import permission
from app.modules.administration.application import permission
from app.core.exceptions.base import ApplicationException
from app.core.validators import apply_shift_time_rules, mobile_number
from app.modules.administration.domain.enums import Role
from app.web.framework.helpers import WebHelper
from app.web.framework.htmx import HTMXBuilder
from app.modules.dependencies import GetHandler
from app.modules.auth.application.command import LoginCommand
from fastapi import Form
from fastapi import Request
from fastapi.responses import RedirectResponse

from app.web.framework.renderer import Renderer

from app.web.auth.presenter import (
    LoginPresenter,
)


class AuthController:

    @staticmethod
    async def login_page(request: Request):
        return Renderer.page(request=request, template="pages/auth/login.html")

    @staticmethod
    async def login_post_page(request: Request):
        command = await WebHelper.bind_form(request=request, model=LoginCommand)
        try:
            result = await GetHandler.login_handler(request).login(command=command)
            if result:
                # Technical Support staff have their own portal and never see the dairy panel
                home = "/support" if Role(int(result.role)) == Role.SUPPORT else "/dashboard"
                res = Renderer.htmx_redirect(url=home)
                res.set_cookie(
                    key="access_token",
                    value="Bearer " + result.access_token,
                    httponly=True,
                    secure=False, # False in local development
                    samesite="lax",
                    path="/",
                )
                return res
            else:
                return Renderer.empty(status_code=401).error("Unauthrized").build()
        except ApplicationException as e:
            # Known login failures (wrong password, disabled account) carry a user-facing message
            return Renderer.partial(request=request, template="components/forms/login_form.html",
             model={"error": e.message}).build()
        except Exception:
            # Anything else is a server fault: log the details, show a short message
            logging.getLogger(__name__).exception("Web login failed")
            return Renderer.partial(request=request, template="components/forms/login_form.html",
             model={"error": "Login failed. Please try again later."}).build()

    @staticmethod
    async def profile_page(request: Request):
        user = request.state.user
        db_manager = request.app.state.application.container.database
        
        from app.modules.dependencies import GetHandler
        profile_service = GetHandler.profile_service(request)
        
        # Load full profile (User, Address, BankAccount)
        profile = await profile_service.get_profile(user_id=user.id)
        payment_service = GetHandler.payment_posting_service(request)
        balance = 0.00
        try:
            balance = await payment_service.get_user_balance(user.id)
        except Exception:
            pass

        edit_url = None
        view_url = None
        from sqlalchemy import select
        if user.role_type in (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN):
            edit_url = f"/sub-admins/edit/{user.id}"
            view_url = f"/sub-admins/view/{user.id}"
        elif user.role_type == Role.MCC:
            from app.modules.mcc.infrastructure.models import MccModel
            mcc_id = await db_manager.session.scalar(select(MccModel.id).where(MccModel.user_id == user.id))
            if mcc_id:
                edit_url = f"/mcc/edit/{mcc_id}"
                view_url = f"/mcc/view/{mcc_id}"
        elif user.role_type == Role.VLCC:
            from app.modules.vlcc.infrastructure.models import VlccModel
            vlcc_id = await db_manager.session.scalar(select(VlccModel.id).where(VlccModel.user_id == user.id))
            if vlcc_id:
                edit_url = f"/vlcc/edit/{vlcc_id}"
                view_url = f"/vlcc/view/{vlcc_id}"
        elif user.role_type == Role.FARMER:
            from app.modules.farmer.infrastructure.models import FarmerModel
            farmer_id = await db_manager.session.scalar(select(FarmerModel.id).where(FarmerModel.user_id == user.id))
            if farmer_id:
                edit_url = f"/farmer/edit/{farmer_id}"
                view_url = f"/farmer/view/{farmer_id}"
                
        return Renderer.page(
            request=request,
            template="pages/auth/profile.html",
            model={
                "user": profile.user,
                "address": profile.address,
                "bank": profile.bank_account,
                "creator_name": profile.user.owner_name or "System / Auto-registered",
                "balance": balance,
                # Everyone edits their own profile through the restricted self-service form
                "edit_url": "/profile/edit",
                "view_url": view_url,
                # Excel column order of the collection exports (Phase 24): managers only
                "column_layout_url": (
                    "/sub-admins/column-layout"
                    if user.role_type in (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN) else None
                ),
            }
        )

    # =========================================================
    # SELF-SERVICE PROFILE EDIT
    #
    # Only name, email, mobile, address and bank details. Settings only for
    # MCC / VLCC users whose settings have `settings_edit_enabled`; the
    # permission flags themselves are never editable here.
    # =========================================================

    @staticmethod
    async def _own_settings(request: Request):
        """The logged-in MCC / VLCC user's settings, or None."""
        from sqlalchemy import select
        from app.modules.mcc.infrastructure.models import MccModel
        from app.modules.vlcc.infrastructure.models import VlccModel

        user = request.state.user
        model = {Role.MCC: MccModel, Role.VLCC: VlccModel}.get(user.role_type)
        if model is None:
            return None
        db = request.app.state.application.container.database
        settings_id = await db.session.scalar(select(model.settings_id).where(model.user_id == user.id))
        if settings_id is None:
            return None
        try:
            return await GetHandler.settings_handler(request).get_by_id(settings_id=settings_id)
        except Exception:
            return None

    @staticmethod
    async def _render_profile_edit(request: Request, error: str | None = None, form: dict | None = None):
        from app.modules.common.settings.domain.enums import (
            AnalyzerType, CattleType, CollectionMode, PrinterType, ReceiptSize, WeightUnit,
        )

        profile = await GetHandler.profile_service(request).get_profile(user_id=request.state.user.id)
        settings = await AuthController._own_settings(request)
        return Renderer.page(
            request=request,
            template="pages/auth/profile_edit.html",
            model={
                "user": profile.user,
                "address": profile.address,
                "bank": profile.bank_account,
                "settings": settings,
                "can_edit_settings": bool(settings and settings.settings_edit_enabled),
                "error": error,
                "form": form or {},
                "options": {
                    "analyzer_type": AnalyzerType,
                    "collection_mode": CollectionMode,
                    "weight_unit": WeightUnit,
                    "receipt_size": ReceiptSize,
                    "printer_type": PrinterType,
                    "cattle_type": CattleType,
                },
            },
        )

    @staticmethod
    async def profile_edit_page(request: Request):
        return await AuthController._render_profile_edit(request)

    @staticmethod
    async def profile_edit_post(request: Request):
        from app.modules.administration.application.command import UpdateUserCommand
        from app.modules.common.address.application.command import CreateAddressCommand, UpdateAddressCommand
        from app.modules.common.bank.application.command import CreateBankAccountCommand, UpdateBankAccountCommand
        from app.modules.common.settings.application.command import UpdateSettingsCommand
        from app.modules.common.settings.domain.enums import (
            AnalyzerType, CattleType, CollectionMode, PrinterType, ReceiptSize, WeightUnit,
        )

        user = request.state.user
        form = dict(await request.form())
        profile_service = GetHandler.profile_service(request)
        existing = await profile_service.get_profile(user_id=user.id)

        name = (form.get("name") or "").strip()
        email = (form.get("email") or "").strip().lower()
        if not name or not email:
            return await AuthController._render_profile_edit(request, "Name and email are required.", form)
        # Mobile is mandatory (10 digits); email and mobile stay unique (own values excluded)
        try:
            mobile = mobile_number(form.get("mobile"), required=True)
        except ValueError as exc:
            return await AuthController._render_profile_edit(request, f"{exc}.", form)
        try:
            await profile_service.ensure_contact_available(
                email=email,
                mobile=mobile,
                exclude_user_id=user.id,
            )
        except ApplicationException as exc:
            return await AuthController._render_profile_edit(request, exc.message, form)

        # Role / status / owner stay exactly as they are
        user_command = UpdateUserCommand(
            id=user.id,
            name=name,
            email=email,
            mobile=mobile,
            role=existing.user.role,
            is_active=True,
            password_hash=None,
            profile_image=None,
        )

        address_fields = dict(
            line=form.get("address_line") or "",
            city=form.get("city") or "",
            state=form.get("state") or "",
            pincode=form.get("pincode") or "",
        )
        bank_fields = dict(
            account_holder=form.get("account_holder") or name,
            bank_name=form.get("bank_name") or "",
            account_number=form.get("account_number") or "",
            ifsc_code=(form.get("ifsc_code") or "").upper(),
            upi_id=form.get("upi_id") or None,
        )
        has_address = any(address_fields.values())
        has_bank = any(v for k, v in bank_fields.items() if k != "account_holder")

        address_command = (
            UpdateAddressCommand(id=existing.address.id, **address_fields)
            if has_address and existing.address else None
        )
        bank_command = (
            UpdateBankAccountCommand(id=existing.bank_account.id, **bank_fields)
            if has_bank and existing.bank_account else None
        )

        # Settings: only when this account is allowed to edit them
        settings_command = None
        settings = await AuthController._own_settings(request)
        if settings and settings.settings_edit_enabled and form.get("settings_submitted"):
            try:
                settings_command = UpdateSettingsCommand(
                    settings_id=settings.id,
                    analyzer_type=AnalyzerType(int(form["analyzer_type"])),
                    analyzer_collection_mode=CollectionMode(int(form["analyzer_collection_mode"])),
                    weight_unit=WeightUnit(int(form["weight_unit"])),
                    weight_collection_mode=CollectionMode(int(form["weight_collection_mode"])),
                    auto_tare_enabled=form.get("auto_tare_enabled") == "on",
                    morning_collection_start=form["morning_collection_start"],
                    morning_collection_end=form["morning_collection_end"],
                    evening_collection_start=form["evening_collection_start"],
                    evening_collection_end=form["evening_collection_end"],
                    receipt_size=ReceiptSize(int(form["receipt_size"])),
                    printer_type=PrinterType(int(form["printer_type"])),
                    printer_enabled=form.get("printer_enabled") == "on",
                    cattle_type=CattleType(int(form["cattle_type"])),
                    # Permission flags are kept as granted by the account's parent
                    max_rate_chart_count=settings.max_rate_chart_count,
                    settings_edit_enabled=settings.settings_edit_enabled,
                    rate_chart_edit_enabled=settings.rate_chart_edit_enabled,
                    master_enabled=settings.master_enabled,
                )
            except (KeyError, ValueError):
                return await AuthController._render_profile_edit(request, "Please fill all settings fields correctly.", form)
            try:
                apply_shift_time_rules(settings_command)
            except ValueError as exc:
                return await AuthController._render_profile_edit(request, str(exc), form)

        async with profile_service._database.transaction():
            await profile_service.update(
                user_data=user_command,
                address_data=address_command,
                bank_data=bank_command,
            )
            if has_address and not existing.address:
                await profile_service.create_address(
                    user_id=user.id, address_data=CreateAddressCommand(**address_fields)
                )
            if has_bank and not existing.bank_account:
                await profile_service.create_bank_account(
                    user_id=user.id, bank_data=CreateBankAccountCommand(user_id=user.id, **bank_fields)
                )
            if settings_command is not None:
                await GetHandler.settings_handler(request).update(settings_command)

        return Renderer.redirect("/profile")

    @staticmethod
    async def logout(request: Request):
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(key="access_token")
        return response