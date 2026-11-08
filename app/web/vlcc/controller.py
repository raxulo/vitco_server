"""
VLCC Web Controller
"""

from app.core.exceptions.base import ForbiddenException
from app.modules.vlcc.application.handler import VlccHandler
from app.modules.vlcc.presentation.requests import UpdateVlccRequest
from app.modules.vlcc.presentation.requests import CreateVlccRequest
from app.modules.ratechart.application.command import GetAssignmentsByOwnerQuery

from uuid import UUID

from fastapi import Request
from fastapi.responses import HTMLResponse

from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.administration.domain.enums import Role
from app.web.framework.helpers import WebHelper

from app.modules.vlcc.application.command import (
    GetVlccQuery,
    ListVlccQuery,
)
from app.modules.vlcc.domain.dto import VlccDetailDto

from app.web.framework.renderer import Renderer
from app.web.shared.manager_filter import resolve_manager_filter
from app.web.vlcc.assembler import VlccAssembler


class VlccController:

    __slots__ = ()

    # =========================================================
    # LIST
    # =========================================================

    @staticmethod
    async def list_page(
        request: Request,
        page: int = 1,
        limit: int = 10,
        search: str = "",
        admin_id: str = "",
        sub_admin_id: str = "",
    ):
        WebHelper.deny_farmer_vlcc(request)
        handler = GetHandler.vlcc_handler(request)

        # Super Admin: Admin + Sub Admin dropdowns; Admin: its Sub Admins
        filters = await resolve_manager_filter(
            request, admin_id=admin_id, sub_admin_id=sub_admin_id, with_sub_admins=True
        )

        result = await handler.list(
            ListVlccQuery(
                page=page,
                size=limit,
                keyword=search.strip(),
                owner=request.state.user,
                manager=filters.manager,
            )
        )

        total_items = await handler.count(
            keyword=search.strip(), owner=request.state.user, manager=filters.manager
        )
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1

        return Renderer.page(
            request=request,
            template="pages/vlcc/list.html",
            model={
                "items": result,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
                "filters": filters,
            },
        )

    @staticmethod
    async def create_page(request: Request):
        WebHelper.deny_farmer_vlcc(request)
        user: CurrentUser = request.state.user
        try:
            VlccHandler.ensure_can_create(user)
        except PermissionError as exc:
            raise ForbiddenException(str(exc))
        routes = await GetHandler.route_master_handler(request).selectable(user)
        return Renderer.page(
            request=request,
            template="pages/vlcc/create_edit.html",
            model={
                "routes": routes,
            },
        )

    # =========================================================
    # EDIT PAGE
    # =========================================================

    @staticmethod
    async def edit_page(
        request: Request,
        vlcc_id: UUID,
    ):
        WebHelper.deny_role(request, Role.VLCC)
        handler = GetHandler.vlcc_handler(request)

        detail: VlccDetailDto = await handler.get_full_detail(
            GetVlccQuery(id=vlcc_id, owner=request.state.user)
        )
        # An MCC sees its creator's VLCCs (suppliers) but edits only the VLCCs it created
        if request.state.user.role_type == Role.MCC and not detail.vlcc.can_modify:
            raise ForbiddenException("This VLCC can be viewed and used, but not modified.")

        versions = []
        try:
            versions = await GetHandler.device_item_version_handler(request).get_by_device_id(detail.user.id)
        except Exception as e:
            print("Error fetching device item versions", e)

        routes = await GetHandler.route_master_handler(request).selectable(request.state.user)

        return Renderer.page(
            request=request,
            template="pages/vlcc/create_edit.html",
            model={
                "vlcc": detail.vlcc,
                "user": detail.user,
                "address": detail.address,
                "bank_account": detail.bank_account,
                "setting": detail.setting,
                "milk_quality_config": detail.milk_quality_config,
                "routes": routes,
                "device_item_versions": versions,
            },
        )

    # =========================================================
    # VIEW PAGE
    # =========================================================

    @staticmethod
    async def view_page(
        request: Request,
        vlcc_id: UUID,
    ):
        user = request.state.user
        handler = GetHandler.vlcc_handler(request)

        detail: VlccDetailDto = await handler.get_full_detail(
            GetVlccQuery(id=vlcc_id, owner=user)
        )

        versions = []
        try:
            versions = await GetHandler.device_item_version_handler(request).get_by_device_id(detail.user.id)
        except Exception as e:
            print("Error fetching device item versions", e)

        rate_charts = []
        try:
            rate_charts = await GetHandler.ratechart_handler(request).get_charts_by_owner_id(
                GetAssignmentsByOwnerQuery(owner_id=detail.user.id)
            )
        except Exception as e:
            print("Error fetching rate charts", e)

        return Renderer.page(
            request=request,
            template="pages/vlcc/view.html",
            model={
                "vlcc": detail.vlcc,
                "user": detail.user,
                "address": detail.address,
                "bank_account": detail.bank_account,
                "setting": detail.setting,
                "milk_quality_config": detail.milk_quality_config,
                "device_item_versions": versions,
                "rate_charts": rate_charts,
            },
        )

    # =========================================================
    # CREATE
    # =========================================================

    @staticmethod
    async def create(request: Request):
        WebHelper.deny_farmer_vlcc(request)
        current_user: CurrentUser = request.state.user

        form_data = await request.form()
        item_names = form_data.getlist("item_names") or form_data.getlist("item_names[]")
        versions = form_data.getlist("versions") or form_data.getlist("versions[]")

        data = CreateVlccRequest.model_validate(form_data)

        command = VlccAssembler.create(
            data=data,
            created_by=current_user.id,
        )

        if item_names and versions:
            from app.modules.common.device_item_version.application.command import DeviceItemVersionInput
            command.device_item_versions = [
                DeviceItemVersionInput(item_name=name, version=ver)
                for name, ver in zip(item_names, versions)
                if name.strip() and ver.strip()
            ]

        handler = GetHandler.vlcc_handler(request)

        result = await handler.full_create(command, owner=current_user)

        if result:
            return Renderer.htmx_redirect("/vlcc")

        return Renderer.empty().error(
            "Unable to create VLCC"
        ).build()

    # =========================================================
    # UPDATE
    # =========================================================

    @staticmethod
    async def update(
        request: Request,
        vlcc_id: UUID,
    ):
        WebHelper.deny_farmer_vlcc(request)
        WebHelper.deny_role(request, Role.VLCC)
        current_user: CurrentUser = request.state.user

        form_data = await request.form()
        item_names = form_data.getlist("item_names") or form_data.getlist("item_names[]")
        versions = form_data.getlist("versions") or form_data.getlist("versions[]")

        data = UpdateVlccRequest.model_validate(form_data)

        command = VlccAssembler.update(
            data=data,
            vlcc_id=vlcc_id,
            updated_by=current_user.id,
        )

        if item_names and versions:
            from app.modules.common.device_item_version.application.command import DeviceItemVersionInput
            command.device_item_versions = [
                DeviceItemVersionInput(item_name=name, version=ver)
                for name, ver in zip(item_names, versions)
                if name.strip() and ver.strip()
            ]
        else:
            command.device_item_versions = []

        handler = GetHandler.vlcc_handler(request)

        result = await handler.update(command, owner=current_user)

        if result:
            return Renderer.htmx_redirect(
                f"/vlcc/view/{vlcc_id}"
            )

        return Renderer.empty().error(
            "Unable to update VLCC"
        ).build()

    # =========================================================
    # CODE VALIDATION
    # =========================================================

    @staticmethod
    async def validate_code(request: Request, vlcc_code: str):
        handler = GetHandler.vlcc_handler(request)

        is_available = await handler.validate_code(
            vlcc_code.strip(), owner=request.state.user
        )

        if is_available:
            return HTMLResponse(
                '<h6 style="color:green">Code available</h6>'
            )

        return HTMLResponse(
            '<h6 style="color:red">Code already exists</h6>'
        )

    @staticmethod
    async def validate_uic_code(request: Request, uic_code: str):
        handler = GetHandler.vlcc_handler(request)

        is_available = await handler.validate_uic_code(
            uic_code.strip(), owner=request.state.user
        )

        if is_available:
            return HTMLResponse('<h6 style="color:green">Code available</h6>')

        return HTMLResponse('<h6 style="color:red">Code already exists</h6>')

    @staticmethod
    async def get_vlccs_by_mcc(request: Request, mcc_id: UUID):
        handler = GetHandler.vlcc_handler(request)

        result = await handler.get_vlccs_by_mcc(
            mcc_id=mcc_id,
            owner=request.state.user,
        )

        return result

    @staticmethod
    async def post_delete(request: Request, id: UUID):
        WebHelper.deny_farmer_vlcc(request)
        from fastapi.responses import RedirectResponse, Response
        from app.modules.vlcc.application.command import DeleteVlccCommand
        
        user: CurrentUser = request.state.user
        handler = GetHandler.vlcc_handler(request)
        try:
            await handler.delete(DeleteVlccCommand(id=id, deleted_by=user.id, owner=user))
        except Exception as e:
            print("Error deleting VLCC:", e)
            if request.headers.get("HX-Request"):
                return Renderer.empty(status_code=400).error(str(e)).build()
            pass

        redirect_url = request.query_params.get("redirect")
        if request.headers.get("HX-Request"):
            if redirect_url:
                return Response(headers={"HX-Redirect": redirect_url})
            return Renderer.empty().success("Successfully deleted").build()

        return RedirectResponse("/vlcc", status_code=303)

    # =========================================================
    # PRIVATE
    # =========================================================

    # @staticmethod
    # async def _routes(request: Request):
    #     handler = GetHandler.route_master_handler(request)

    #     result = await handler.list(
    #         ListRouteMasterQuery(size=200)
    #     )

    #     return result.items