"""
Auth Web Controller
"""

from app.core.exceptions.base import ForbiddenException
from app.modules.mcc.application.handler import MccHandler
from app.modules.mcc.presentation.requests import UpdateMccRequest
from app.modules.ratechart.application.command import ListRateChartsQuery
from app.core.exceptions.base import ValidateError
from app.core.exceptions.base import ApplicationException
from app.modules.administration.domain.enums import Role
from app.modules.mcc.application.command import ListMccQuery
from app.web.mcc.assembler import MccAssembler
from app.modules.mcc.presentation.requests import CreateMccRequest
from app.middleware.authentication import CurrentUser
from fastapi.responses import HTMLResponse
from app.modules.mcc.domain.dto import MccDetailDto
from app.modules.mcc.application.command import GetMccQuery
from uuid import UUID
from app.modules.dependencies import GetHandler
from app.web.framework.helpers import WebHelper
from fastapi import Request

from app.web.framework.renderer import Renderer


class MccController:

    @staticmethod
    async def page(request: Request, page: int = 1, limit: int = 10, search: str = ""):
        user:CurrentUser = request.state.user
        if int(user.role) >= Role.MCC.value:
            raise ForbiddenException("You are not authorized to access this page")
        handler = GetHandler.mcc_handler(request)
        query: ListMccQuery = ListMccQuery(
            page=page, size=limit, keyword=search, owner=user
        )   
        items = await handler.list(query=query)
        total_items = await handler.count(search, owner=user)
        total_pages = (total_items + limit - 1) // limit if total_items > 0 else 1
        
        return Renderer.page(
            request=request, 
            template="pages/mcc/list.html", 
            model={
                "items": items,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
                "search": search,
            }
        )
    
    @staticmethod
    async def get_create_page(request: Request):
        user: CurrentUser = request.state.user
        try:
            MccHandler.ensure_can_create(user)
        except PermissionError as exc:
            raise ForbiddenException(str(exc))
        routes = await GetHandler.route_master_handler(request).selectable(user)
        return Renderer.page(
            request=request, 
            template="pages/mcc/create_edit.html", 
            model={
                "routes": routes,
            }
        )

    @staticmethod
    async def get_edit_page(request: Request, id: UUID):
        WebHelper.deny_role(request, Role.MCC)
        query: GetMccQuery = GetMccQuery(
            id=id, owner=request.state.user
        )
        result: MccDetailDto = await GetHandler.mcc_handler(request).get_full_detail(query=query)
        versions = []
        try:
            versions = await GetHandler.device_item_version_handler(request).get_by_device_id(result.user.id)
        except Exception as e:
            print("Error fetching device item versions", e)

        routes = await GetHandler.route_master_handler(request).selectable(request.state.user)

        model_dict = {
            "mcc": result.mcc,
            "user": result.user,
            "bank_account": result.bank_account,
            "address": result.address,
            "setting": result.setting,
            "milk_quality_config": result.milk_quality_config,
            "fixed_rate_config": result.fixed_rate_config,
            "device_item_versions": versions,
            "routes": routes,
        }

        return Renderer.page(
            request=request, 
            template="pages/mcc/create_edit.html", 
            model=model_dict
        )

    @staticmethod
    async def view_page(request: Request, id: UUID):
        query: GetMccQuery = GetMccQuery(
            id=id, owner=request.state.user
        )
        result: MccDetailDto = await GetHandler.mcc_handler(request).get_full_detail(query=query)
        versions = []
        try:
            versions = await GetHandler.device_item_version_handler(request).get_by_device_id(result.user.id)
        except Exception as e:
            print("Error fetching device item versions", e)

        rate_charts = []
        try:
            rate_charts = await GetHandler.ratechart_handler(request).list(
                ListRateChartsQuery(page=1, size=100,owner=CurrentUser(
                    id=result.user.id,role=Role.MCC, name="", permissions=frozenset()
                ))
            )
        except Exception as e:
            print("Error fetching rate charts", e)

        model_dict = {
            "user": result.user,
            "mcc": result.mcc,
            "bank_account": result.bank_account,
            "address": result.address,
            "setting": result.setting,
            "milk_quality_config": result.milk_quality_config,
            "fixed_rate_config": result.fixed_rate_config,
            "device_item_versions": versions,
            "rate_charts": rate_charts,
        }

        return Renderer.page(
            request=request, 
            template="pages/mcc/view.html", 
            model=model_dict
        )

    @staticmethod
    async def post_create_page(request: Request):
        user: CurrentUser = request.state.user

        form_data = await request.form()
        print("DEBUG ALL FORM ITEMS:", list(form_data.multi_items()))
        item_names = form_data.getlist("item_names") or form_data.getlist("item_names[]")
        versions = form_data.getlist("versions") or form_data.getlist("versions[]")

        data = CreateMccRequest.model_validate(form_data)
        command = MccAssembler.create(data, user.id)


        if item_names and versions:
            from app.modules.common.device_item_version.application.command import DeviceItemVersionInput
            command.device_item_versions = [
                DeviceItemVersionInput(item_name=name, version=ver)
                for name, ver in zip(item_names, versions)
                if name.strip() and ver.strip()
            ]
            print("DEBUG FORM SUBMIT - command device item versions:", command.device_item_versions)

        result = await GetHandler.mcc_handler(request).full_create(command, owner=user)

        if result:
            return Renderer.htmx_redirect(url="/mcc")
        else:
            return Renderer.empty().error("Unproceble Error").build()

    @staticmethod
    async def post_update_page(request: Request,  id: UUID):
        WebHelper.deny_role(request, Role.MCC)
        user: CurrentUser = request.state.user

        form_data = await request.form()
        item_names = form_data.getlist("item_names") or form_data.getlist("item_names[]")
        versions = form_data.getlist("versions") or form_data.getlist("versions[]")

        data = UpdateMccRequest.model_validate(form_data)
        command = MccAssembler.update(data, id, user.id)

        if item_names and versions:
            from app.modules.common.device_item_version.application.command import DeviceItemVersionInput
            command.device_item_versions = [
                DeviceItemVersionInput(item_name=name, version=ver)
                for name, ver in zip(item_names, versions)
                if name.strip() and ver.strip()
            ]
        else:
            command.device_item_versions = []

        result = await GetHandler.mcc_handler(request).full_update(command, owner=user)

        if result:
            return Renderer.htmx_redirect(url=f"/mcc/view/{id}")
        else:
            return Renderer.empty().error("Unproceble Error").build()


    @staticmethod
    async def edit_post(request: Request, id: UUID):

        user: CurrentUser = request.state.user

        form_data = await request.form()
        data_dict = dict(form_data)
        item_names = form_data.getlist("item_names") or form_data.getlist("item_names[]")
        versions = form_data.getlist("versions") or form_data.getlist("versions[]")

        data = CreateMccRequest.model_validate(data_dict)
        command = MccAssembler.update(data, id, user.id)

        if item_names and versions:
            from app.modules.common.device_item_version.application.command import DeviceItemVersionInput
            command.device_item_versions = [
                DeviceItemVersionInput(item_name=name, version=ver)
                for name, ver in zip(item_names, versions)
                if name.strip() and ver.strip()
            ]
        else:
            command.device_item_versions = []

        try:
            await GetHandler.mcc_handler(request).full_update(command=command, owner=user)
            return Renderer.redirect(url="/mcc")
        except Exception as e:
            query = GetMccQuery(id=id, owner=user)
            result = await GetHandler.mcc_handler(request).get_full_detail(query=query)
            return Renderer.page(
                request=request,
                template="pages/mcc/create_edit.html",
                model={"mcc_data": result, "error": str(e)}
            )

    @staticmethod
    async def validate_code(request: Request, code: str):
        user: CurrentUser = request.state.user
        result: bool = await GetHandler.mcc_handler(request).validate_code(code, user)
        return HTMLResponse("<h6 style=\"color: green\">Code available</h6>" if result else "<h6 style=\"color: red\">Code already exists</h6>")

    @staticmethod
    async def post_delete(request: Request, id: UUID):
        from fastapi.responses import RedirectResponse, Response
        from app.modules.mcc.application.command import DeleteMccCommand
        
        user: CurrentUser = request.state.user
        handler = GetHandler.mcc_handler(request)
        try:
            await handler.delete(DeleteMccCommand(id=id, deleted_by=user.id, owner=user))
        except Exception as e:
            print("Error deleting MCC:", e)
            if request.headers.get("HX-Request"):
                return Renderer.empty(status_code=400).error(str(e)).build()
            pass

        redirect_url = request.query_params.get("redirect")
        if request.headers.get("HX-Request"):
            if redirect_url:
                return Response(headers={"HX-Redirect": redirect_url})
            return Renderer.empty().success("Successfully deleted").build()

        return RedirectResponse("/mcc", status_code=303)


    
