"""
Auth Web Controller
"""

from app.modules.administration.application import permission
from app.modules.administration.application import permission
from app.modules.administration.application import permission
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
            print("KKKKK: ", result)
            if result:
                res = Renderer.htmx_redirect(url="/dashboard")
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
        except Exception as e:
            return Renderer.partial(request=request, template="components/forms/login_form.html",
             model={"error": str(e)}).build()

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
                "edit_url": edit_url,
                "view_url": view_url,
            }
        )

    @staticmethod
    async def logout(request: Request):
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(key="access_token")
        return response